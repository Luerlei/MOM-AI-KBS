"""时序预测服务

包含：
- 数据预处理（缺失值插值、异常值检测截断）
- 预测执行（调用 ForecastClient + 统计基线模型对比）
- 未来时间标签生成（基于历史频率外推）
- 基础统计算法（趋势方向、强度、增长率、波动性）
- 扩展评估指标（MAE/MAPE/RMSE/MASE/sMAPE/Pinball/Coverage/rMAE）
- 交叉验证（滚动/扩展窗口多次回测）
- 多模型对比回测
- LLM 自然语言分析报告
- TokenUsage 日志记录
"""
import json
import logging
import math
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Dataset, ForecastTask, ForecastResult, TokenUsage, ModelConfig
from app.services.dataset_service import _load_series
from app.utils.response import APIError

logger = logging.getLogger(__name__)


# ==================== 预测执行 ====================

async def run_forecast(db: Session, dataset_id: int, horizon: int,
                       quantiles: list = None, start_index: int = None,
                       skip_analysis: bool = False, is_internal: bool = False,
                       train_window: int = None) -> dict:
    """执行预测

    Args:
        start_index: 回测起点。若设置，则用前 start_index 个点作为训练数据预测，
                     与后续实际值对照。None 表示从末尾预测未来。
        skip_analysis: 跳过 LLM 分析报告生成（节省 ~20s），仅用模板摘要。
        is_internal: 内部任务标记（交叉验证/模型对比），不在任务历史中展示。
        train_window: 滑动窗口大小。设置时仅使用 start_index 前 train_window 个点训练
                      （实现真正的滑动窗口，而非扩展窗口）。

    Returns:
        {
            "task": {id, status, ...},
            "result": {forecasts, quantiles, future_times, model_name, analysis, ...}
        }
    """
    from app.services.llm_client import ModelManager

    # 1. 读取数据集
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    series = _load_series(ds.series_data)
    if len(series) < 3:
        raise APIError(f"数据点数 {len(series)} 不足，至少需要 3 个", status_code=400)

    full_values = [p["value"] for p in series]
    full_times = [p.get("time", "") for p in series]

    # 回测模式：先拆分再预处理（避免测试数据泄漏到预处理中）
    is_backtest = start_index is not None and start_index < len(full_values)
    train_offset = 0  # N6: 滑动窗口时的训练数据起始偏移
    if is_backtest:
        if start_index < 3:
            raise APIError("回测起点至少需要 3 个训练点", status_code=400)
        # 仅在训练集上预处理（避免数据泄漏）
        train_raw = full_values[:start_index]
        # N6: 滑动窗口模式 - 仅使用最后 train_window 个点作为训练数据
        if train_window is not None and train_window > 0 and train_window < len(train_raw):
            train_offset = len(train_raw) - train_window
            train_raw = train_raw[-train_window:]
        preprocess_info = _preprocess_series(train_raw, ds.frequency)
        values = preprocess_info["values"]
        if preprocess_info["outliers_fixed"] > 0 or preprocess_info["missing_filled"] > 0:
            for i, v in enumerate(values):
                series[train_offset + i]["value"] = v
        times = full_times[train_offset:start_index]
        # 实际对照值（不预处理，保持原始值用于评估）
        actual_count = min(horizon, len(full_values) - start_index)
        actual_values = full_values[start_index:start_index + actual_count]
        actual_times = full_times[start_index:start_index + actual_count]
        effective_horizon = actual_count
    else:
        # 非回测：全量预处理
        preprocess_info = _preprocess_series(full_values, ds.frequency)
        full_values = preprocess_info["values"]
        if preprocess_info["outliers_fixed"] > 0 or preprocess_info["missing_filled"] > 0:
            for i, v in enumerate(full_values):
                series[i]["value"] = v
        values = full_values
        times = full_times
        actual_values = []
        actual_times = []
        effective_horizon = horizon

    # 2. 获取启用的 Forecast 模型
    forecast_client = ModelManager.get_active_forecast()
    model_config = (
        db.query(ModelConfig)
        .filter(ModelConfig.type == "Forecast", ModelConfig.is_active == True)  # noqa: E712
        .first()
    )

    # 3. 创建任务记录
    task = ForecastTask(
        dataset_id=dataset_id,
        model_config_id=model_config.id if model_config else None,
        model_name=forecast_client.model_name,
        horizon=effective_horizon,
        start_index=start_index if is_backtest else None,
        status="running",
        is_internal=1 if is_internal else 0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    start = time.time()
    try:
        # 4. 调用 ForecastClient（用训练数据预测）
        result = await forecast_client.predict(
            series=values,
            horizon=effective_horizon,
            quantiles=quantiles or [0.1, 0.5, 0.9],
        )
        duration_ms = int((time.time() - start) * 1000)

        # 5. 生成未来时间标签（基于训练数据的时间序列外推）
        if is_backtest:
            # 回测模式：未来时间使用实际时间标签
            future_times = actual_times
        else:
            future_times = _generate_future_times(times, effective_horizon, ds.frequency)

        # 6. 基础统计分析（基于训练数据）
        stats = _compute_stats(values)

        # 6.5 季节性分解（STL）+ 异常点统计
        # N6: 滑动窗口模式下，labels_train 需要从 train_offset 开始取
        labels_train = [p.get("label", "") for p in series[train_offset:train_offset + len(values)]]
        labels_full = [p.get("label", "") for p in series]
        anomaly_indices = [i for i, l in enumerate(labels_train) if l and str(l).strip()]
        decomposition = _stl_decompose(values, ds.frequency)

        # 6.6 回测模式：异常点误差统计
        anomaly_stats = {}
        if is_backtest and actual_values and labels_full:
            # N6: 滑动窗口模式下 len(values) != start_index，用 start_index 定位实际值标签
            actual_labels = labels_full[start_index:start_index + len(actual_values)]
            anomaly_actual_indices = [i for i, l in enumerate(actual_labels) if l and str(l).strip()]
            if anomaly_actual_indices:
                fc_used_tmp = result["forecasts"][:len(actual_values)]
                # N11: 使用 min 长度避免 IndexError；N13: 跳过 None 值
                n_cmp = min(len(fc_used_tmp), len(actual_values))
                anom_set = set(anomaly_actual_indices)
                anom_errs = []
                normal_errs = []
                for i in range(n_cmp):
                    av = actual_values[i]
                    fv = fc_used_tmp[i]
                    if av is None or fv is None:
                        continue
                    e = abs(av - fv)
                    if i in anom_set:
                        anom_errs.append(e)
                    else:
                        normal_errs.append(e)
                if anom_errs or normal_errs:
                    anomaly_stats = {
                        "anomaly_count": len(anomaly_actual_indices),
                        "anomaly_avg_error": round(sum(anom_errs) / len(anom_errs), 4) if anom_errs else 0,
                        "normal_avg_error": round(sum(normal_errs) / len(normal_errs), 4) if normal_errs else 0,
                        "error_ratio": round((sum(anom_errs) / len(anom_errs)) / (sum(normal_errs) / len(normal_errs)), 2) if normal_errs and sum(normal_errs) > 0 else 0,
                    }

        # 7. 回测误差计算（含扩展指标 + 基线对比）
        metrics = {}
        if is_backtest and actual_values:
            fc_used = result["forecasts"][:len(actual_values)]
            quantiles_used = result.get("quantiles", {})
            # N13: 过滤掉 actuals 为 None 的位置，避免 _compute_metrics 崩溃
            clean_actuals = []
            clean_fc = []
            for av, fv in zip(actual_values, fc_used):
                if av is not None and fv is not None:
                    clean_actuals.append(av)
                    clean_fc.append(fv)
            if clean_actuals:
                metrics = _compute_metrics(
                    clean_actuals, clean_fc, values, quantiles_used, ds.frequency
                )
                if anomaly_stats:
                    metrics["anomaly_stats"] = anomaly_stats

        # 8. LLM 分析报告（可跳过以加速）
        if skip_analysis:
            analysis_text = _build_summary_text(stats, ds.frequency, ds.unit)
        else:
            analysis_text = await _generate_llm_analysis(
                ds_name=ds.name,
                frequency=ds.frequency,
                unit=ds.unit,
                times=times,
                values=values,
                forecasts=result["forecasts"],
                future_times=future_times,
                quantiles=result.get("quantiles", {}),
                stats=stats,
                is_backtest=is_backtest,
                actual_values=actual_values,
                metrics=metrics,
                db=db,
                labels=labels_train,
                anomaly_indices=anomaly_indices,
                decomposition=decomposition,
            )

        # 9. 存预测结果
        fc_result = ForecastResult(
            task_id=task.id,
            dataset_id=dataset_id,
            forecasts=json.dumps(result["forecasts"], ensure_ascii=False),
            quantiles=json.dumps(result.get("quantiles", {}), ensure_ascii=False),
            future_times=json.dumps(future_times, ensure_ascii=False),
            actuals=json.dumps(actual_values, ensure_ascii=False),
            metrics=json.dumps(metrics, ensure_ascii=False),
            model_name=result.get("model", forecast_client.model_name),
            analysis=analysis_text,
        )
        db.add(fc_result)

        # 10. 更新任务状态
        task.status = "success"
        task.duration_ms = duration_ms
        task.completed_at = datetime.utcnow().isoformat()
        db.commit()
        db.refresh(fc_result)

        # 11. 记录 TokenUsage 日志
        _log_forecast_usage(
            db,
            model_name=result.get("model", forecast_client.model_name),
            input_points=len(values),
            output_points=len(result["forecasts"]),
            duration_ms=duration_ms,
        )

        return {
            "task": _task_to_out(task),
            "result": _result_to_out(fc_result),
        }

    except Exception as e:
        # 失败：更新任务状态
        duration_ms = int((time.time() - start) * 1000)
        # 先 rollback 清除 session 的错误状态，避免 PendingRollbackError
        db.rollback()
        task.status = "failed"
        task.error_message = str(e)[:500]
        task.duration_ms = duration_ms
        task.completed_at = datetime.utcnow().isoformat()
        db.commit()

        # 记录失败日志
        _log_forecast_usage(
            db,
            model_name=forecast_client.model_name,
            input_points=len(values),
            output_points=0,
            duration_ms=duration_ms,
            success=False,
        )

        if isinstance(e, APIError):
            raise
        raise APIError(f"预测失败: {e}", status_code=500)


# ==================== 查询 ====================

def get_tasks(db: Session, dataset_id: int = None, page: int = 1,
              page_size: int = 20) -> dict:
    """获取预测任务历史（过滤掉内部任务：交叉验证/模型对比）"""
    q = db.query(ForecastTask).filter(
        (ForecastTask.is_internal == 0) | (ForecastTask.is_internal.is_(None))
    )
    if dataset_id:
        q = q.filter(ForecastTask.dataset_id == dataset_id)
    q = q.order_by(ForecastTask.id.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_task_to_out(t) for t in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_latest_result(db: Session, dataset_id: int) -> dict:
    """获取数据集最新预测结果（过滤掉内部回测任务，避免回测结果被当作未来预测返回）"""
    task = (
        db.query(ForecastTask)
        .filter(
            ForecastTask.dataset_id == dataset_id,
            ForecastTask.status == "success",
            (ForecastTask.is_internal == 0) | (ForecastTask.is_internal.is_(None)),
        )
        .order_by(ForecastTask.id.desc())
        .first()
    )
    if not task:
        return None
    result = (
        db.query(ForecastResult)
        .filter(ForecastResult.task_id == task.id)
        .first()
    )
    if not result:
        return None
    return {
        "task": _task_to_out(task),
        "result": _result_to_out(result),
    }


def get_result_by_task(db: Session, task_id: int) -> dict:
    """按 task_id 获取特定预测任务的结果（用于历史任务查看）"""
    task = db.query(ForecastTask).filter(ForecastTask.id == task_id).first()
    if not task:
        raise APIError("预测任务不存在", status_code=404)
    result = (
        db.query(ForecastResult)
        .filter(ForecastResult.task_id == task_id)
        .first()
    )
    if not result:
        raise APIError("该任务暂无预测结果", status_code=404)
    return {
        "task": _task_to_out(task),
        "result": _result_to_out(result),
    }


def get_trend_analysis(db: Session, dataset_id: int) -> dict:
    """获取趋势分析聚合数据（历史 + 最新预测 + 统计分析）"""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)

    series = _load_series(ds.series_data)
    values = [p["value"] for p in series]
    history = [{"time": p.get("time", ""), "value": p["value"], "label": p.get("label", "")} for p in series]

    stats = _compute_stats(values)

    # 最新预测结果
    latest = get_latest_result(db, dataset_id)
    forecast_data = None
    if latest:
        r = latest["result"]
        t = latest["task"]
        forecast_data = {
            "forecasts": r["forecasts"],
            "quantiles": r["quantiles"],
            "future_times": r["future_times"],
            "actuals": r.get("actuals", []),
            "metrics": r.get("metrics", {}),
            "model_name": r["model_name"],
            "duration_ms": t["duration_ms"],
            "analysis": r["analysis"],
            "task_id": t["id"],
            "start_index": t.get("start_index"),
            "horizon": t["horizon"],
            "is_backtest": t.get("start_index") is not None,
        }

    return {
        "dataset": {
            "id": ds.id,
            "name": ds.name,
            "description": ds.description or "",
            "frequency": ds.frequency,
            "unit": ds.unit or "",
            "point_count": ds.point_count,
        },
        "history": history,
        "forecast": forecast_data,
        "analysis": {
            "stats": stats,
            "summary": _build_summary_text(stats, ds.frequency, ds.unit),
        },
    }


def get_result_for_export(db: Session, task_id: int) -> dict:
    """获取预测结果用于导出"""
    task = db.query(ForecastTask).filter(ForecastTask.id == task_id).first()
    if not task:
        raise APIError("预测任务不存在", status_code=404)
    result = db.query(ForecastResult).filter(ForecastResult.task_id == task_id).first()
    if not result:
        raise APIError("预测结果不存在", status_code=404)
    ds = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
    return {
        "dataset_name": ds.name if ds else "",
        "frequency": ds.frequency if ds else "other",
        "unit": ds.unit if ds else "",
        "series_data": _load_series(ds.series_data) if ds else [],
        "forecasts": json.loads(result.forecasts) if result.forecasts else [],
        "future_times": json.loads(result.future_times) if result.future_times else [],
        "quantiles": json.loads(result.quantiles) if result.quantiles else {},
        "actuals": json.loads(result.actuals) if result.actuals else [],
        "metrics": json.loads(result.metrics) if result.metrics else {},
        "start_index": task.start_index,
    }


# ==================== 内部工具 ====================

def _task_to_out(task: ForecastTask) -> dict:
    return {
        "id": task.id,
        "dataset_id": task.dataset_id,
        "model_config_id": task.model_config_id,
        "model_name": task.model_name,
        "horizon": task.horizon,
        "start_index": task.start_index,
        "status": task.status,
        "error_message": task.error_message or "",
        "duration_ms": task.duration_ms,
        "created_at": task.created_at,
        "completed_at": task.completed_at or "",
    }


def _result_to_out(r: ForecastResult) -> dict:
    return {
        "id": r.id,
        "task_id": r.task_id,
        "dataset_id": r.dataset_id,
        "forecasts": json.loads(r.forecasts) if r.forecasts else [],
        "quantiles": json.loads(r.quantiles) if r.quantiles else {},
        "future_times": json.loads(r.future_times) if r.future_times else [],
        "actuals": json.loads(r.actuals) if r.actuals else [],
        "metrics": json.loads(r.metrics) if r.metrics else {},
        "model_name": r.model_name,
        "analysis": r.analysis or "",
        "created_at": r.created_at,
    }


def _log_forecast_usage(db: Session, model_name: str, input_points: int,
                        output_points: int, duration_ms: int, success: bool = True):
    """记录预测调用的 TokenUsage 日志"""
    try:
        usage = TokenUsage(
            call_type="forecast",
            model_name=model_name,
            input_tokens=input_points,
            output_tokens=output_points,
            duration_ms=duration_ms,
            source="trend_analysis" if success else "trend_analysis_failed",
        )
        db.add(usage)
        db.commit()
    except Exception:
        db.rollback()


# ==================== 未来时间标签生成 ====================

def _generate_future_times(history_times: list, horizon: int, frequency: str) -> list:
    """基于历史时间标签和频率，外推生成未来时间标签

    策略：
    1. 月/季度/年频率：解析最后日期，用月份算术外推（避免 timedelta 跨月漂移）
    2. 日/周/小时频率：解析最后两个点间隔，用 timedelta 外推
    3. 全部失败时返回 t1, t2, ...
    """
    if not history_times:
        return [f"t{i+1}" for i in range(horizon)]

    last_time = history_times[-1]
    last_dt = _parse_date(last_time)

    # 月/季度/年：使用月份算术（避免 30/90/365 天漂移）
    month_step_map = {"monthly": 1, "quarterly": 3, "yearly": 12}
    if frequency in month_step_map and last_dt:
        step = month_step_map[frequency]
        future = []
        cur_y, cur_m = last_dt.year, last_dt.month
        for _ in range(horizon):
            cur_m += step
            while cur_m > 12:
                cur_m -= 12
                cur_y += 1
            future.append(_format_ym(cur_y, cur_m, frequency))
        return future

    # 日/周/小时：用最后两点的间隔外推
    prev_time = history_times[-2] if len(history_times) >= 2 else None
    if last_dt and prev_time:
        prev_dt = _parse_date(prev_time)
        if prev_dt:
            delta = last_dt - prev_dt
            if delta.total_seconds() > 0:
                future = []
                cur = last_dt
                for _ in range(horizon):
                    cur = cur + delta
                    future.append(_format_date(cur, frequency))
                return future

    # 按 frequency 推断（日/周/小时）
    if last_dt:
        delta_map = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "hourly": timedelta(hours=1),
        }
        delta = delta_map.get(frequency)
        if delta:
            future = []
            cur = last_dt
            for _ in range(horizon):
                cur = cur + delta
                future.append(_format_date(cur, frequency))
            return future

    # 回退：序号
    import re
    m = re.search(r"(\d+)$", last_time)
    base = int(m.group(1)) if m else len(history_times)
    return [f"t{base + i + 1}" for i in range(horizon)]


def _format_ym(year: int, month: int, frequency: str) -> str:
    """按频率格式化 年/月 组合"""
    if frequency == "yearly":
        return f"{year}"
    if frequency == "quarterly":
        q = (month - 1) // 3 + 1
        return f"{year}-Q{q}"
    return f"{year}-{month:02d}"


def _parse_date(s: str):
    """尝试解析多种日期格式"""
    s = str(s).strip()
    formats = [
        "%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m",
        "%Y年%m月", "%Y年%m月%d日",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # 尝试季度格式 "YYYY-QN"
    import re
    qm = re.match(r"^(\d{4})-Q([1-4])$", s)
    if qm:
        year = int(qm.group(1))
        month = (int(qm.group(2)) - 1) * 3 + 1
        return datetime(year, month, 1)
    # 尝试纯年份
    try:
        if len(s) == 4 and s.isdigit():
            return datetime(int(s), 1, 1)
    except ValueError:
        pass
    return None


def _format_date(dt: datetime, frequency: str) -> str:
    """按频率格式化日期（用于日/周/小时频率）"""
    fmt_map = {
        "daily": "%Y-%m-%d",
        "weekly": "%Y-%m-%d",
        "hourly": "%Y-%m-%d %H:00",
    }
    fmt = fmt_map.get(frequency, "%Y-%m-%d")
    return dt.strftime(fmt)


# ==================== 基础统计算法 ====================

def _compute_stats(values: list) -> dict:
    """计算基础统计指标

    Returns:
        {
            count, min, max, avg, first, last,
            trend_direction: up/down/flat,
            trend_strength: 0-1 (线性回归 R²),
            growth_rate: 平均环比增长率 %,
            volatility: 变异系数 %,
        }
    """
    n = len(values)
    if n == 0:
        return {}

    mn, mx = min(values), max(values)
    avg = sum(values) / n
    first, last = values[0], values[-1]

    # 线性回归（最小二乘法）求趋势
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = avg
    num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    den_x = sum((x - x_mean) ** 2 for x in xs)
    den_y = sum((y - y_mean) ** 2 for y in values)
    slope = num / den_x if den_x > 0 else 0
    r_squared = (num ** 2) / (den_x * den_y) if (den_x > 0 and den_y > 0) else 0

    # 趋势方向
    if abs(slope) < 1e-9 or r_squared < 0.1:
        trend_direction = "flat"
    elif slope > 0:
        trend_direction = "up"
    else:
        trend_direction = "down"

    # 平均增长率（几何平均：基于首末值 (last/first)^(1/(n-1))-1，避免算术平均环比偏差）
    growth_rate = 0.0
    if n >= 2:
        first_v, last_v = values[0], values[-1]
        if first_v > 0 and last_v > 0 and all(v > 0 for v in values):
            # 几何平均增长率
            growth_rate = round(((last_v / first_v) ** (1.0 / (n - 1)) - 1) * 100, 2)
        else:
            # 含零或负值时回退到算术平均环比
            rates = []
            for i in range(1, n):
                prev = values[i - 1]
                if abs(prev) > 1e-9:
                    rates.append((values[i] - prev) / prev * 100)
            if rates:
                growth_rate = round(sum(rates) / len(rates), 2)

    # 变异系数（波动性）：用 abs(avg) 避免均值为负时返回负值
    variance = sum((y - y_mean) ** 2 for y in values) / n
    std = math.sqrt(variance)
    volatility = round(std / abs(avg) * 100, 2) if abs(avg) > 1e-9 else 0.0

    return {
        "count": n,
        "min": round(mn, 2),
        "max": round(mx, 2),
        "avg": round(avg, 2),
        "first": round(first, 2),
        "last": round(last, 2),
        "trend_direction": trend_direction,
        "trend_strength": round(r_squared, 3),
        "growth_rate": growth_rate,
        "volatility": volatility,
    }


def _build_summary_text(stats: dict, frequency: str, unit: str) -> str:
    """构建模板化摘要文案（基础统计，非 LLM）"""
    if not stats:
        return "数据不足，无法生成摘要。"

    dir_map = {"up": "上升", "down": "下降", "flat": "平稳"}
    dir_text = dir_map.get(stats["trend_direction"], "平稳")
    freq_map = {
        "daily": "日", "weekly": "周", "monthly": "月",
        "quarterly": "季度", "yearly": "年", "hourly": "小时", "other": "期",
    }
    freq_text = freq_map.get(frequency, "期")
    unit_text = unit or ""

    parts = [
        f"数据共 {stats['count']} 个数据点，"
        f"范围 {stats['min']}{unit_text} ~ {stats['max']}{unit_text}，"
        f"均值 {stats['avg']}{unit_text}，末值 {stats['last']}{unit_text}。",
        f"趋势呈{dir_text}（R²={stats['trend_strength']}），",
        f"平均{freq_text}环比增长 {stats['growth_rate']}%，",
        f"波动性（变异系数）{stats['volatility']}%。",
    ]
    return "".join(parts)


def _compute_metrics(actuals: list, forecasts: list,
                     train_values: list = None,
                     quantiles: dict = None,
                     frequency: str = "other") -> dict:
    """计算回测误差指标（含扩展指标 + 基线对比）

    Args:
        actuals: 实际值列表
        forecasts: 预测值列表
        train_values: 训练数据（用于计算 MASE 的 Naive 误差分母）
        quantiles: 分位数预测 {"0.1": [...], "0.9": [...]}（用于 Pinball Loss 和 Coverage）
        frequency: 数据频率（用于确定 SeasonalNaive 周期）

    Returns:
        {
            "mae", "mape", "rmse", "max_error",           # 基础指标
            "mase", "smape",                               # 扩展点预测指标
            "pinball_loss", "coverage",                    # 概率预测指标
            "rmae",                                        # 相对 Naive 基线
            "baselines": {naive_mae, seasonal_naive_mae},  # 基线模型误差
        }
    """
    n = min(len(actuals), len(forecasts))
    if n == 0:
        return {}

    errors = [actuals[i] - forecasts[i] for i in range(n)]
    abs_errors = [abs(e) for e in errors]
    mae = sum(abs_errors) / n

    # MAPE
    mape_values = []
    for i in range(n):
        if abs(actuals[i]) > 1e-9:
            mape_values.append(abs(errors[i]) / abs(actuals[i]) * 100)
    mape = sum(mape_values) / len(mape_values) if mape_values else 0.0

    # RMSE
    mse = sum(e ** 2 for e in errors) / n
    rmse = math.sqrt(mse)

    # sMAPE（对称百分比误差）
    smape_values = []
    for i in range(n):
        denom = abs(actuals[i]) + abs(forecasts[i])
        if denom > 1e-9:
            smape_values.append(abs(errors[i]) / denom * 200)
    smape = sum(smape_values) / len(smape_values) if smape_values else 0.0

    # ===== 基线模型预测 =====
    season = _get_seasonal_period(frequency)
    naive_fc = _naive_predict(train_values, n)
    seasonal_naive_fc = _seasonal_naive_predict(train_values, n, season)

    # 基线误差
    naive_mae = _simple_mae(actuals, naive_fc)
    seasonal_naive_mae = _simple_mae(actuals, seasonal_naive_fc)

    # MASE = 模型 MAE / Naive 一步预测 MAE
    mase = 0.0
    if train_values and len(train_values) >= 2:
        # Naive 一步误差：用训练数据自身计算
        naive_errors = [abs(train_values[i] - train_values[i - 1]) for i in range(1, len(train_values))]
        naive_mae_train = sum(naive_errors) / len(naive_errors) if naive_errors else 0
        if naive_mae_train > 1e-9:
            mase = mae / naive_mae_train

    # rMAE = 模型 MAE / Naive 预测 MAE
    rmae = mae / naive_mae if naive_mae > 1e-9 else 0.0

    # Pinball Loss（分位数预测质量）
    pinball_loss = 0.0
    if quantiles:
        total_loss = 0.0
        count = 0
        for q_str, q_forecasts in quantiles.items():
            q = float(q_str)
            q_fc = q_forecasts[:n] if isinstance(q_forecasts, list) else []
            for i in range(min(n, len(q_fc))):
                diff = actuals[i] - q_fc[i]
                loss = q * diff if diff >= 0 else (q - 1) * diff
                total_loss += loss
                count += 1
        pinball_loss = total_loss / count if count > 0 else 0.0

    # Coverage（实际值落在预测区间内的比例）
    coverage = 0.0
    if quantiles and "0.1" in quantiles and "0.9" in quantiles:
        p10 = quantiles["0.1"][:n] if isinstance(quantiles["0.1"], list) else []
        p90 = quantiles["0.9"][:n] if isinstance(quantiles["0.9"], list) else []
        if p10 and p90:
            in_range = sum(1 for i in range(min(n, len(p10), len(p90)))
                           if p10[i] <= actuals[i] <= p90[i])
            coverage = in_range / min(n, len(p10), len(p90)) * 100

    result = {
        "mae": round(mae, 4),
        "mape": round(mape, 2),
        "rmse": round(rmse, 4),
        "max_error": round(max(abs_errors), 4),
        "smape": round(smape, 2),
        "mase": round(mase, 4),
        "rmae": round(rmae, 4),
        "pinball_loss": round(pinball_loss, 4),
        "coverage": round(coverage, 2),
        "baselines": {
            "naive_mae": round(naive_mae, 4),
            "seasonal_naive_mae": round(seasonal_naive_mae, 4),
        },
    }
    return result


# ==================== LLM 自然语言分析 ====================

async def _generate_llm_analysis(ds_name: str, frequency: str, unit: str,
                                  times: list, values: list,
                                  forecasts: list, future_times: list,
                                  quantiles: dict, stats: dict,
                                  is_backtest: bool = False,
                                  actual_values: list = None,
                                  metrics: dict = None,
                                  db: Session = None,
                                  labels: list = None,
                                  anomaly_indices: list = None,
                                  decomposition: dict = None) -> str:
    """调用 LLM 生成自然语言趋势分析报告

    无 LLM 配置时回退到模板化摘要。
    记录 TokenUsage 日志（call_type=trend_analysis, source=trend_analysis）。
    """
    from app.services.llm_client import model_manager, ModelManager

    # 基础摘要作为兜底
    fallback = _build_summary_text(stats, frequency, unit)

    try:
        llm = model_manager.get_active_llm()
    except APIError:
        # 未配置 LLM，使用基础摘要
        return fallback

    # 构造分析 prompt
    freq_map = {
        "daily": "每日", "weekly": "每周", "monthly": "每月",
        "quarterly": "每季度", "yearly": "每年", "hourly": "每小时", "other": "每期",
    }
    freq_text = freq_map.get(frequency, "每期")
    unit_text = unit or "（无单位）"

    # 动态采样历史数据（按频率决定采样点数）
    history_str = _sample_history_for_prompt(times, values, frequency)

    forecast_str = ", ".join(f"{t}:{round(f, 2)}" for t, f in zip(future_times, forecasts))

    p10 = quantiles.get("0.1", [])
    p90 = quantiles.get("0.9", [])
    interval_str = ""
    if p10 and p90:
        interval_str = f"\n- 预测 10% 下界: {', '.join(str(round(x, 2)) for x in p10)}"
        interval_str += f"\n- 预测 90% 上界: {', '.join(str(round(x, 2)) for x in p90)}"

    # 异常点信息
    anomaly_section = ""
    anomaly_requirements = ""
    if anomaly_indices:
        anomaly_points = []
        for idx in anomaly_indices[:10]:  # 最多展示10个
            t = times[idx] if idx < len(times) else f"#{idx}"
            v = values[idx] if idx < len(values) else "?"
            lbl = labels[idx] if labels and idx < len(labels) else ""
            anomaly_points.append(f"{t}({v}, 标注:{lbl})")
        anomaly_section = f"""
## 异常点标注（用户标注的异常数据点）
- 异常点数量: {len(anomaly_indices)}
- 异常点详情: {', '.join(anomaly_points)}
"""
        anomaly_requirements = """
- **异常点专项分析**：结合用户标注的异常点，分析异常原因、对预测的影响、是否需要剔除"""

    # STL 分解结果
    decomp_section = ""
    if decomposition and decomposition.get("success"):
        decomp_section = f"""
## 季节性分解（STL）
- 趋势分量末值: {round(decomposition.get('trend_last', 0), 2)}
- 季节分量振幅: {round(decomposition.get('seasonal_amplitude', 0), 2)}
- 残差标准差: {round(decomposition.get('residual_std', 0), 2)}
- 季节性强度: {round(decomposition.get('seasonal_strength', 0), 2)}（0-1，越接近1季节性越强）
"""

    # 回测模式附加信息
    backtest_section = ""
    backtest_requirements = ""
    if is_backtest and actual_values:
        actual_str = ", ".join(f"{t}:{round(a, 2)}" for t, a in zip(future_times, actual_values))
        compare_str = ", ".join(
            f"{t}: 预测{round(forecasts[i], 2)} vs 实际{round(actual_values[i], 2)} (误差{round(actual_values[i] - forecasts[i], 2)})"
            for i, t in enumerate(future_times) if i < len(actual_values)
        )
        m = metrics or {}
        baseline_section = ""
        if "baselines" in m:
            bl = m["baselines"]
            baseline_section = f"""
- 统计基线对比：
  - Naive 基线 MAE={bl.get('naive_mae', 'N/A')}{unit_text}
  - SeasonalNaive 基线 MAE={bl.get('seasonal_naive_mae', 'N/A')}{unit_text}
  - rMAE（模型/Naive）={m.get('rmae', 'N/A')}（<1 优于 Naive，>1 不如 Naive）
  - MASE={m.get('mase', 'N/A')}（<1 优于季节性朴素基准）
"""
        # 异常点误差统计
        anomaly_error_section = ""
        if "anomaly_stats" in m:
            ans = m["anomaly_stats"]
            anomaly_error_section = f"""
- 异常点误差分析：异常点平均误差={ans.get('anomaly_avg_error', 'N/A')}{unit_text}，正常点平均误差={ans.get('normal_avg_error', 'N/A')}{unit_text}，误差比={ans.get('error_ratio', 'N/A')}（>1 说明模型在异常点表现更差）
"""
        backtest_section = f"""
## 回测对照结果
- 预测起点：前 {len(values)} 个点作为训练数据
- 实际值：{actual_str}
- 逐点对比：{compare_str}
- 误差指标：MAE={m.get('mae', 0)}{unit_text}, MAPE={m.get('mape', 0)}%, RMSE={m.get('rmse', 0)}{unit_text}, 最大误差={m.get('max_error', 0)}{unit_text}
- 扩展指标：MASE={m.get('mase', 'N/A')}, sMAPE={m.get('smape', 'N/A')}%, Pinball={m.get('pinball_loss', 'N/A')}, Coverage={m.get('coverage', 'N/A')}%{baseline_section}{anomaly_error_section}
"""
        backtest_requirements = """
5. **回测精度评估**：模型预测与实际值的偏差分析、哪几个点偏差最大及可能原因、模型适用性评价、与 Naive 基线的优劣对比"""

    prompt = f"""你是时序数据分析专家。请基于以下数据生成简洁的中文趋势分析报告。

## 数据集信息
- 名称: {ds_name}
- 频率: {freq_text}
- 单位: {unit_text}

## 历史数据
{history_str}

## 统计指标
- 数据点数: {stats.get('count', 0)}
- 最小值: {stats.get('min', 0)}, 最大值: {stats.get('max', 0)}, 均值: {stats.get('avg', 0)}
- 首值: {stats.get('first', 0)}, 末值: {stats.get('last', 0)}
- 趋势方向: {stats.get('trend_direction', 'unknown')}（R²={stats.get('trend_strength', 0)}）
- 平均环比增长率: {stats.get('growth_rate', 0)}%
- 波动性（变异系数）: {stats.get('volatility', 0)}%
{decomp_section}{anomaly_section}
## 预测结果（未来{len(forecasts)}步）
{forecast_str}{interval_str}
{backtest_section}
## 要求
请用 3-5 段话输出分析报告，包含：
1. **历史趋势概述**：数据整体走势、关键转折点、季节性模式（如有）
2. **波动性分析**：数据稳定性、异常点（如有 label 标注）
3. **预测解读**：预测值的含义、置信区间宽窄、可能的风险
4. **建议**：基于分析给出 1-2 条行动建议
{backtest_requirements}{anomaly_requirements}
直接输出报告正文，不要加标题和额外说明。"""

    messages = [
        {"role": "system", "content": "你是专业的时序数据分析专家，擅长用简洁中文撰写分析报告。"},
        {"role": "user", "content": prompt},
    ]

    try:
        llm_start = time.time()
        # 使用流式调用：thinking 模型（如 DeepSeek-V4-Flash）非流式会 >120s 超时
        # 流式模式下收到 HTTP 200 头即可确认连通，thinking 阶段逐步 yield 不会超时
        chunks = []
        async for piece in llm.chat_stream(messages):
            chunks.append(piece)
        llm_duration = int((time.time() - llm_start) * 1000)
        content = "".join(chunks).strip()

        # 记录 LLM 调用的 TokenUsage 日志
        # 流式模式下从 llm.last_usage 读取 token（chat_stream 在最后一个 chunk 设置）
        if db is not None:
            usage = getattr(llm, "last_usage", {}) or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            model_name = usage.get("model", llm.model_name)
            try:
                log = TokenUsage(
                    call_type="trend_analysis",
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=llm_duration,
                    source="trend_analysis",
                )
                db.add(log)
                db.commit()
            except Exception:
                db.rollback()

        return content if content else fallback
    except Exception:
        logger.exception(f"[forecast._generate_llm_analysis] LLM 分析失败，使用基础摘要兜底 dataset_id 可能受影响")
        return fallback


# ==================== 数据预处理 ====================

def _preprocess_series(values: list, frequency: str = "other") -> dict:
    """数据预处理管道：缺失值插值 + 异常值检测截断

    Returns:
        {
            "values": 处理后的值列表,
            "missing_filled": 填充的缺失值数,
            "outliers_fixed": 截断的异常值数,
        }
    """
    result = list(values)
    missing_filled = 0
    outliers_fixed = 0

    # 1. 缺失值检测与线性插值（None/NaN 视为缺失）
    for i in range(len(result)):
        v = result[i]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            result[i] = None
            missing_filled += 1
    # 线性插值填充
    if missing_filled > 0:
        result = _linear_interpolate(result)

    # 2. 异常值检测（IQR 方法）+ 截断到上下界
    if len(result) >= 4:
        sorted_vals = sorted(result)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        for i in range(len(result)):
            if result[i] < lower_bound:
                result[i] = lower_bound
                outliers_fixed += 1
            elif result[i] > upper_bound:
                result[i] = upper_bound
                outliers_fixed += 1

    return {
        "values": result,
        "missing_filled": missing_filled,
        "outliers_fixed": outliers_fixed,
    }


def _linear_interpolate(values: list) -> list:
    """对含 None 的列表进行线性插值"""
    result = list(values)
    n = len(result)
    for i in range(n):
        if result[i] is not None:
            continue
        # 找前一个非空值
        prev_idx = i - 1
        while prev_idx >= 0 and result[prev_idx] is None:
            prev_idx -= 1
        # 找后一个非空值
        next_idx = i + 1
        while next_idx < n and result[next_idx] is None:
            next_idx += 1
        if prev_idx >= 0 and next_idx < n:
            # 线性插值
            ratio = (i - prev_idx) / (next_idx - prev_idx)
            result[i] = result[prev_idx] + (result[next_idx] - result[prev_idx]) * ratio
        elif prev_idx >= 0:
            result[i] = result[prev_idx]  # 前向填充
        elif next_idx < n:
            result[i] = result[next_idx]  # 后向填充
    return result


# ==================== 统计基线模型 ====================

def _get_seasonal_period(frequency: str) -> int:
    """根据数据频率推断季节周期"""
    period_map = {
        "hourly": 24,
        "daily": 7,
        "weekly": 52,
        "monthly": 12,
        "quarterly": 4,
        "yearly": 1,
        "other": 1,
    }
    return period_map.get(frequency, 1)


def _naive_predict(train_values: list, horizon: int) -> list:
    """Naive 基线：预测值 = 最后一个观测值"""
    if not train_values:
        return [0.0] * horizon
    last_val = train_values[-1]
    return [last_val] * horizon


def _seasonal_naive_predict(train_values: list, horizon: int, season: int = 1) -> list:
    """SeasonalNaive 基线：预测值 = 去年同期值"""
    if not train_values:
        return [0.0] * horizon
    n = len(train_values)
    if season <= 0 or season >= n:
        # 无法取同期，退化为 Naive
        return _naive_predict(train_values, horizon)
    forecasts = []
    for i in range(horizon):
        idx = n - season + (i % season)
        if idx >= 0 and idx < n:
            forecasts.append(train_values[idx])
        else:
            forecasts.append(train_values[-1])
    return forecasts


def _simple_mae(actuals: list, forecasts: list) -> float:
    """简单 MAE 计算"""
    n = min(len(actuals), len(forecasts))
    if n == 0:
        return 0.0
    return sum(abs(actuals[i] - forecasts[i]) for i in range(n)) / n


# ==================== 交叉验证 ====================

async def run_cross_validation(db: Session, dataset_id: int,
                               n_splits: int = 5,
                               horizon: int = 6,
                               strategy: str = "expanding",
                               skip_analysis: bool = True) -> dict:
    """交叉验证：多次回测取平均

    Args:
        n_splits: 回测次数
        horizon: 每次回测的预测步数
        strategy: "expanding"（扩展窗口）或 "sliding"（滑动窗口）
        skip_analysis: 跳过 LLM 分析以加速

    Returns:
        {
            "splits": [{split_idx, start_index, metrics, duration_ms}, ...],
            "avg_metrics": {mae, mape, rmse, mase, rmae, ...},
            "std_metrics": {mae, mape, rmse, mase, rmae, ...},
            "model_name": str,
        }
    """
    from app.services.llm_client import ModelManager

    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    series = _load_series(ds.series_data)
    total_len = len(series)
    min_train = 3

    # 计算最小数据量要求
    min_required = min_train + horizon * n_splits
    if total_len < min_train + horizon:
        raise APIError(
            f"数据点数 {total_len} 不足，交叉验证至少需要 {min_train + horizon} 个点（{min_train} 训练 + {horizon}×1 预测）",
            status_code=400,
        )

    # 生成切分点
    splits = []
    cv_train_window = None  # N6: 滑动窗口模式下的训练窗口大小
    if strategy == "sliding":
        # 滑动窗口：固定训练窗口大小，窗口滑动
        # 训练窗口 = 总长度 - horizon * n_splits
        cv_train_window = max(min_train, total_len - horizon * n_splits)
        for i in range(n_splits):
            start_idx = cv_train_window + i * horizon
            if start_idx + horizon > total_len:
                break
            splits.append(start_idx)
    else:
        # 扩展窗口：起点固定或递增，终点逐步前进
        # 均匀分布 n_splits 个切分点
        available = total_len - min_train - horizon
        if available <= 0:
            raise APIError("数据量不足以进行交叉验证", status_code=400)
        step = max(1, available // max(1, n_splits))
        for i in range(n_splits):
            start_idx = min_train + i * step
            if start_idx + horizon > total_len:
                break
            splits.append(start_idx)

    if not splits:
        raise APIError("无法生成有效的交叉验证切分", status_code=400)

    # 执行多次回测
    results = []
    forecast_client = ModelManager.get_active_forecast()
    model_name = forecast_client.model_name

    for split_idx, si in enumerate(splits):
        split_start = time.time()
        try:
            result = await run_forecast(
                db, dataset_id=dataset_id, horizon=horizon,
                start_index=si, skip_analysis=skip_analysis,
                is_internal=True,
                train_window=cv_train_window,  # N6: 滑动窗口时传入训练窗口大小
            )
            metrics = result["result"].get("metrics", {})
            duration_ms = int((time.time() - split_start) * 1000)
            results.append({
                "split_idx": split_idx,
                "start_index": si,
                "metrics": metrics,
                "duration_ms": duration_ms,
                "status": "success",
            })
        except Exception as e:
            results.append({
                "split_idx": split_idx,
                "start_index": si,
                "metrics": {},
                "duration_ms": int((time.time() - split_start) * 1000),
                "status": "failed",
                "error": str(e)[:200],
            })

    # 计算平均和标准差
    successful = [r for r in results if r["status"] == "success" and r["metrics"]]
    avg_metrics = {}
    std_metrics = {}
    if successful:
        # 收集所有数值型指标（排除嵌套的 baselines）
        metric_keys = [k for k in successful[0]["metrics"].keys()
                       if k != "baselines" and isinstance(successful[0]["metrics"].get(k), (int, float))]
        for key in metric_keys:
            vals = [r["metrics"].get(key, 0) for r in successful]
            avg_metrics[key] = round(sum(vals) / len(vals), 4)
            if len(vals) > 1:
                variance = sum((v - avg_metrics[key]) ** 2 for v in vals) / len(vals)
                std_metrics[key] = round(math.sqrt(variance), 4)
            else:
                std_metrics[key] = 0.0
        # baselines 平均
        bl_keys = ["naive_mae", "seasonal_naive_mae"]
        avg_bl = {}
        std_bl = {}
        for bk in bl_keys:
            vals = [r["metrics"].get("baselines", {}).get(bk, 0) for r in successful]
            avg_bl[bk] = round(sum(vals) / len(vals), 4)
            if len(vals) > 1:
                variance = sum((v - avg_bl[bk]) ** 2 for v in vals) / len(vals)
                std_bl[bk] = round(math.sqrt(variance), 4)
            else:
                std_bl[bk] = 0.0
        avg_metrics["baselines"] = avg_bl
        std_metrics["baselines"] = std_bl

    return {
        "splits": results,
        "avg_metrics": avg_metrics,
        "std_metrics": std_metrics,
        "model_name": model_name,
        "strategy": strategy,
        "n_splits": len(results),
        "horizon": horizon,
    }


# ==================== 多模型对比回测 ====================

async def compare_models(db: Session, dataset_id: int,
                         horizon: int = 6,
                         start_index: int = None) -> dict:
    """多模型对比回测：对当前数据集跑所有已配置 Forecast 模型的回测

    Args:
        horizon: 预测步数
        start_index: 回测起点。None 时自动选择 70% 位置

    Returns:
        {
            "models": [{model_name, model_config_id, metrics, duration_ms, status}, ...],
            "best_model": {model_name, metric_name, metric_value},
            "baselines": {naive_mae, seasonal_naive_mae},  # 基线参考
        }
    """
    from app.services.llm_client import ModelManager

    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    series = _load_series(ds.series_data)
    total_len = len(series)
    if total_len < 6:
        raise APIError(f"数据点数 {total_len} 不足，多模型对比至少需要 6 个点", status_code=400)

    # 自动选择回测起点（70% 位置）
    if start_index is None:
        start_index = max(3, int(total_len * 0.7))
    actual_count = min(horizon, total_len - start_index)
    if actual_count < 1:
        raise APIError("回测起点超出数据范围", status_code=400)

    # 获取所有已配置的 Forecast 模型
    all_models = (
        db.query(ModelConfig)
        .filter(ModelConfig.type == "Forecast")
        .order_by(ModelConfig.id)
        .all()
    )
    if not all_models:
        raise APIError("没有已配置的 Forecast 模型", status_code=400)

    # 获取训练数据和实际值
    # N4: 不对全量数据预处理，actual_values 使用原始值（与 run_forecast 评估方式一致），
    #     仅对训练集预处理后用于基线计算，保证基线与模型评估目标一致
    full_values = [p["value"] for p in series]
    train_raw = full_values[:start_index]
    actual_values = full_values[start_index:start_index + actual_count]  # 原始值

    # 基线参考：仅在训练集上预处理（与 run_forecast 的回测模式一致）
    preprocess_info = _preprocess_series(train_raw, ds.frequency)
    train_processed = preprocess_info["values"]

    season = _get_seasonal_period(ds.frequency)
    naive_fc = _naive_predict(train_processed, actual_count)
    seasonal_naive_fc = _seasonal_naive_predict(train_processed, actual_count, season)
    baselines = {
        "naive_mae": round(_simple_mae(actual_values, naive_fc), 4),
        "seasonal_naive_mae": round(_simple_mae(actual_values, seasonal_naive_fc), 4),
        "naive_forecasts": naive_fc,
        "seasonal_naive_forecasts": seasonal_naive_fc,
    }

    # 对每个模型执行回测
    model_results = []
    original_active_id = None
    active_model = (
        db.query(ModelConfig)
        .filter(ModelConfig.type == "Forecast", ModelConfig.is_active == True)  # noqa: E712
        .first()
    )
    if active_model:
        original_active_id = active_model.id

    for mc in all_models:
        model_start = time.time()
        try:
            # 临时切换激活模型
            if original_active_id != mc.id:
                # 先取消所有激活
                db.query(ModelConfig).filter(ModelConfig.type == "Forecast").update(
                    {ModelConfig.is_active: False}
                )
                mc.is_active = True
                db.commit()
                # 重新加载 ModelManager
                ModelManager.reload_forecast(db)

            # 执行回测（跳过 LLM 分析）
            result = await run_forecast(
                db, dataset_id=dataset_id, horizon=horizon,
                start_index=start_index, skip_analysis=True,
                is_internal=True,
            )
            metrics = result["result"].get("metrics", {})
            duration_ms = int((time.time() - model_start) * 1000)
            model_results.append({
                "model_name": mc.name,
                "model_config_id": mc.id,
                "model_identifier": mc.model_name,
                "metrics": metrics,
                "duration_ms": duration_ms,
                "status": "success",
            })
        except Exception as e:
            model_results.append({
                "model_name": mc.name,
                "model_config_id": mc.id,
                "model_identifier": mc.model_name,
                "metrics": {},
                "duration_ms": int((time.time() - model_start) * 1000),
                "status": "failed",
                "error": str(e)[:200],
            })

    # 恢复原来的激活模型
    if original_active_id:
        db.query(ModelConfig).filter(ModelConfig.type == "Forecast").update(
            {ModelConfig.is_active: False}
        )
        db.query(ModelConfig).filter(ModelConfig.id == original_active_id).update(
            {ModelConfig.is_active: True}
        )
        db.commit()
        ModelManager.reload_forecast(db)

    # 找出最优模型（按 MAE 最低）
    best_model = None
    successful_models = [m for m in model_results if m["status"] == "success" and m["metrics"]]
    if successful_models:
        best = min(successful_models, key=lambda m: m["metrics"].get("mae", float("inf")))
        best_model = {
            "model_name": best["model_name"],
            "metric_name": "mae",
            "metric_value": best["metrics"].get("mae", 0),
            "rmae": best["metrics"].get("rmae", 0),
        }

    return {
        "models": model_results,
        "best_model": best_model,
        "baselines": baselines,
        "start_index": start_index,
        "actual_count": actual_count,
        "horizon": horizon,
    }


# ==================== 历史数据动态采样（P2-2） ====================

def _sample_history_for_prompt(times: list, values: list, frequency: str) -> str:
    """按频率动态采样历史数据，避免 token 过多同时保留关键模式

    策略：
    - 月频/季频/年频：全部展示（通常不超过60个点）
    - 日频：最近30天 + 每月均值
    - 周频：最近52周
    - 小时频：最近48小时 + 每日均值
    - other：最近20个点
    """
    n = len(values)
    if n == 0:
        return "（无历史数据）"

    # 短序列直接全部展示
    if n <= 30:
        return ", ".join(f"{times[i]}:{round(values[i], 2)}" for i in range(n))

    parts = []

    if frequency in ("monthly", "quarterly", "yearly"):
        # 全部展示
        parts.append(", ".join(f"{times[i]}:{round(values[i], 2)}" for i in range(n)))

    elif frequency == "daily":
        # 最近30天 + 每月均值
        recent_n = min(30, n)
        recent_str = ", ".join(f"{times[i]}:{round(values[i], 2)}" for i in range(n - recent_n, n))
        parts.append(f"最近{recent_n}天: {recent_str}")
        # 每月均值（简化：每30天一组）
        monthly_means = []
        for start in range(0, n - recent_n, 30):
            chunk = values[start:start + 30]
            if chunk:
                monthly_means.append(round(sum(chunk) / len(chunk), 2))
        if monthly_means:
            parts.append(f"早期月度均值趋势: {', '.join(str(m) for m in monthly_means)}")

    elif frequency == "weekly":
        # 最近52周
        recent_n = min(52, n)
        recent_str = ", ".join(f"{times[i]}:{round(values[i], 2)}" for i in range(n - recent_n, n))
        parts.append(f"最近{recent_n}周: {recent_str}")

    elif frequency == "hourly":
        # 最近48小时 + 每日均值
        recent_n = min(48, n)
        recent_str = ", ".join(f"{times[i]}:{round(values[i], 2)}" for i in range(n - recent_n, n))
        parts.append(f"最近{recent_n}小时: {recent_str}")
        daily_means = []
        for start in range(0, n - recent_n, 24):
            chunk = values[start:start + 24]
            if chunk:
                daily_means.append(round(sum(chunk) / len(chunk), 2))
        if daily_means:
            parts.append(f"早期日度均值趋势: {', '.join(str(m) for m in daily_means)}")

    else:
        # other：最近20个点
        recent_n = min(20, n)
        recent_str = ", ".join(f"{times[i]}:{round(values[i], 2)}" for i in range(n - recent_n, n))
        parts.append(f"最近{recent_n}个点: {recent_str}")

    return " | ".join(parts)


# ==================== 季节性分解 STL（P2-3） ====================

def _stl_decompose(values: list, frequency: str) -> dict:
    """STL 季节性分解

    Returns:
        {
            "success": bool,
            "trend_last": 趋势分量末值,
            "seasonal_amplitude": 季节分量振幅(max-min),
            "residual_std": 残差标准差,
            "seasonal_strength": 季节性强度(0-1),
            "trend": 趋势分量列表,
            "seasonal": 季节分量列表,
            "residual": 残差分量列表,
        }
    """
    try:
        from statsmodels.tsa.seasonal import STL
        import numpy as np

        period = _get_seasonal_period(frequency)
        if period < 2 or len(values) < 2 * period:
            return {"success": False, "message": "数据量不足或无季节性"}

        # 构造 pandas Series
        import pandas as pd
        s = pd.Series(values, dtype=float)

        stl = STL(s, period=period, robust=True)
        res = stl.fit()

        trend = res.trend.tolist()
        seasonal = res.seasonal.tolist()
        resid = res.resid.tolist()

        # 季节性强度 = max(0, 1 - Var(resid) / Var(seasonal + resid))
        var_resid = float(np.nanvar(resid)) if len(resid) > 0 else 0
        var_seas_resid = float(np.nanvar(np.array(seasonal) + np.array(resid))) if len(seasonal) > 0 else 0
        seasonal_strength = 0.0
        if var_seas_resid > 0:
            seasonal_strength = max(0.0, min(1.0, 1 - var_resid / var_seas_resid))

        # 清理 NaN
        trend_clean = [0.0 if (x is None or (isinstance(x, float) and math.isnan(x))) else x for x in trend]
        seasonal_clean = [0.0 if (x is None or (isinstance(x, float) and math.isnan(x))) else x for x in seasonal]
        resid_clean = [0.0 if (x is None or (isinstance(x, float) and math.isnan(x))) else x for x in resid]

        return {
            "success": True,
            "trend_last": round(trend_clean[-1], 4) if trend_clean else 0,
            "seasonal_amplitude": round(max(seasonal_clean) - min(seasonal_clean), 4) if seasonal_clean else 0,
            "residual_std": round(math.sqrt(sum(r ** 2 for r in resid_clean) / len(resid_clean)), 4) if resid_clean else 0,
            "seasonal_strength": round(seasonal_strength, 4),
            "trend": [round(x, 4) for x in trend_clean],
            "seasonal": [round(x, 4) for x in seasonal_clean],
            "residual": [round(x, 4) for x in resid_clean],
        }
    except Exception as e:
        return {"success": False, "message": f"STL 分解失败: {str(e)[:100]}"}


def get_decomposition(db: Session, dataset_id: int) -> dict:
    """获取数据集的 STL 分解结果（供前端可视化）"""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    series = _load_series(ds.series_data)
    values = [p["value"] for p in series]
    times = [p.get("time", "") for p in series]

    # 预处理
    preprocess_info = _preprocess_series(values, ds.frequency)
    values = preprocess_info["values"]

    decomp = _stl_decompose(values, ds.frequency)
    if not decomp.get("success"):
        return {"success": False, "message": decomp.get("message", "分解失败")}

    return {
        "success": True,
        "times": times,
        "original": values,
        "trend": decomp["trend"],
        "seasonal": decomp["seasonal"],
        "residual": decomp["residual"],
        "seasonal_strength": decomp["seasonal_strength"],
        "seasonal_amplitude": decomp["seasonal_amplitude"],
        "frequency": ds.frequency,
        "preprocess": {
            "missing_filled": preprocess_info["missing_filled"],
            "outliers_fixed": preprocess_info["outliers_fixed"],
        },
    }


# ==================== 统计模型预测（P3-2） ====================

def _arima_predict(train_values: list, horizon: int, order=None) -> dict:
    """ARIMA 模型预测"""
    try:
        from statsmodels.tsa.arima.model import ARIMA
        import numpy as np

        if order is None:
            # 自动选择阶数（简化版：基于 AIC 在小范围搜索）
            best_aic = float("inf")
            best_order = (1, 1, 1)
            for p in range(0, 3):
                for d in range(0, 2):
                    for q in range(0, 3):
                        try:
                            model = ARIMA(train_values, order=(p, d, q))
                            res = model.fit()
                            if res.aic < best_aic:
                                best_aic = res.aic
                                best_order = (p, d, q)
                        except Exception:
                            continue
            order = best_order

        model = ARIMA(train_values, order=order)
        res = model.fit()
        fc = res.forecast(steps=horizon)
        forecasts = [float(x) for x in np.array(fc)]

        # 置信区间
        conf = res.get_forecast(steps=horizon).conf_int(alpha=0.2)
        p10 = [float(x) for x in np.array(conf.iloc[:, 0])]
        p90 = [float(x) for x in np.array(conf.iloc[:, 1])]

        return {
            "forecasts": forecasts,
            "quantiles": {"0.1": p10, "0.5": forecasts, "0.9": p90},
            "model": f"ARIMA{order}",
        }
    except Exception as e:
        raise APIError(f"ARIMA 预测失败: {str(e)[:150]}", status_code=500)


def _ets_predict(train_values: list, horizon: int, frequency: str = "monthly") -> dict:
    """ETS（指数平滑）模型预测"""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        import numpy as np
        import math as _math

        # 自动选择趋势和季节性
        trend_type = "add"
        seasonal_type = None
        season_periods = None

        # 尝试带季节性，失败则退化为无季节
        try:
            season_periods = _get_seasonal_period(frequency) if len(train_values) >= 24 else None
            if season_periods and len(train_values) >= 2 * season_periods:
                model = ExponentialSmoothing(
                    train_values, trend=trend_type, seasonal="add",
                    seasonal_periods=season_periods,
                )
            else:
                model = ExponentialSmoothing(train_values, trend=trend_type)
        except Exception:
            model = ExponentialSmoothing(train_values)

        res = model.fit()
        fc = res.forecast(horizon)
        forecasts = [float(x) for x in np.array(fc)]

        # N18: 置信区间随 horizon 增长（预测误差按 sqrt(h) 缩放）
        resid = res.resid
        std = _math.sqrt(sum(r ** 2 for r in resid) / len(resid)) if len(resid) > 0 else 0
        p10 = [f - 1.28 * std * _math.sqrt(i + 1) for i, f in enumerate(forecasts)]
        p90 = [f + 1.28 * std * _math.sqrt(i + 1) for i, f in enumerate(forecasts)]

        return {
            "forecasts": forecasts,
            "quantiles": {"0.1": p10, "0.5": forecasts, "0.9": p90},
            "model": "ETS",
        }
    except Exception as e:
        raise APIError(f"ETS 预测失败: {str(e)[:150]}", status_code=500)


def _theta_predict(train_values: list, horizon: int) -> dict:
    """Theta 方法预测（标准实现：SES θ=0 + 线性 θ=2 组合）

    标准 Theta 方法：
    1. θ=0 线 = SES（简单指数平滑），预测为常数
    2. θ=2 线 = 线性回归（2×原始 - SES）
    3. 最终预测 = 0.5 × SES预测 + 0.5 × 线性预测
    """
    try:
        import numpy as np
        import math as _math
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        n = len(train_values)
        if n < 2:
            last = float(train_values[-1]) if train_values else 0.0
            return {
                "forecasts": [last] * horizon,
                "quantiles": {"0.1": [last] * horizon, "0.5": [last] * horizon, "0.9": [last] * horizon},
                "model": "Theta",
            }

        # 1. SES 拟合（θ=0 线）
        ses_model = ExponentialSmoothing(train_values, trend=None, seasonal=None)
        ses_res = ses_model.fit()
        ses_fitted = np.array(ses_res.fittedvalues, dtype=float)
        # SES 预测为常数（最后一个平滑值）
        ses_fc_val = float(ses_res.forecast(1)[0])
        ses_forecast = [ses_fc_val] * horizon

        # 2. 线性回归（θ=2 线）
        xs = np.arange(n, dtype=float)
        y_arr = np.array(train_values, dtype=float)
        x_mean = float(np.mean(xs))
        y_mean = float(np.mean(y_arr))
        num = float(np.sum((xs - x_mean) * (y_arr - y_mean)))
        den = float(np.sum((xs - x_mean) ** 2))
        slope = num / den if den > 0 else 0.0
        intercept = y_mean - slope * x_mean
        linear_forecast = [float(intercept + slope * (n + i)) for i in range(horizon)]

        # 3. 组合：标准 Theta 方法取平均
        forecasts = [0.5 * ses_forecast[i] + 0.5 * linear_forecast[i] for i in range(horizon)]

        # 4. 置信区间：用残差标准差，随 horizon 增长（sqrt(h) 缩放）
        linear_fitted = [intercept + slope * i for i in range(n)]
        # 处理 SES 第一个 fitted value 可能为 NaN
        if np.isnan(ses_fitted[0]):
            ses_fitted[0] = float(train_values[0])
        fitted = [0.5 * ses_fitted[i] + 0.5 * linear_fitted[i] for i in range(n)]
        resid = [float(train_values[i]) - fitted[i] for i in range(n)]
        std = _math.sqrt(sum(r ** 2 for r in resid) / n) if n > 0 else 0
        p10 = [f - 1.28 * std * _math.sqrt(i + 1) for i, f in enumerate(forecasts)]
        p90 = [f + 1.28 * std * _math.sqrt(i + 1) for i, f in enumerate(forecasts)]

        return {
            "forecasts": forecasts,
            "quantiles": {"0.1": p10, "0.5": forecasts, "0.9": p90},
            "model": "Theta",
        }
    except Exception as e:
        raise APIError(f"Theta 预测失败: {str(e)[:150]}", status_code=500)


def run_statistical_forecast(db: Session, dataset_id: int, horizon: int,
                             model_type: str = "arima",
                             start_index: int = None) -> dict:
    """执行统计模型预测（ARIMA/ETS/Theta）

    不依赖外部推理服务，纯本地 statsmodels 计算。
    """
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    series = _load_series(ds.series_data)
    if len(series) < 6:
        raise APIError(f"数据点数 {len(series)} 不足，统计模型至少需要 6 个点", status_code=400)

    full_values = [p["value"] for p in series]
    full_times = [p.get("time", "") for p in series]

    # 回测模式：先拆分再预处理（避免数据泄漏）
    is_backtest = start_index is not None and start_index < len(full_values)
    if is_backtest:
        # 仅在训练集上预处理
        train_raw = full_values[:start_index]
        preprocess_info = _preprocess_series(train_raw, ds.frequency)
        values = preprocess_info["values"]
        times = full_times[:start_index]
        actual_count = min(horizon, len(full_values) - start_index)
        actual_values = full_values[start_index:start_index + actual_count]
        actual_times = full_times[start_index:start_index + actual_count]
        effective_horizon = actual_count
    else:
        preprocess_info = _preprocess_series(full_values, ds.frequency)
        full_values = preprocess_info["values"]
        values = full_values
        times = full_times
        actual_values = []
        actual_times = []
        effective_horizon = horizon

    # 选择统计模型
    model_map = {
        "arima": _arima_predict,
        "ets": _ets_predict,
        "theta": _theta_predict,
    }
    if model_type not in model_map:
        raise APIError(f"不支持的统计模型: {model_type}，可选: arima/ets/theta", status_code=400)

    model_name = model_type.upper()
    start = time.time()
    try:
        if model_type == "ets":
            result = _ets_predict(values, effective_horizon, ds.frequency)
        else:
            result = model_map[model_type](values, effective_horizon)
        duration_ms = int((time.time() - start) * 1000)

        # 生成未来时间标签
        if is_backtest:
            future_times = actual_times
        else:
            future_times = _generate_future_times(times, effective_horizon, ds.frequency)

        # 统计分析
        stats = _compute_stats(values)

        # 回测误差
        metrics = {}
        if is_backtest and actual_values:
            metrics = _compute_metrics(
                actual_values, result["forecasts"][:len(actual_values)],
                values, result.get("quantiles", {}), ds.frequency
            )

        # 存任务和结果
        task = ForecastTask(
            dataset_id=dataset_id,
            model_config_id=None,
            model_name=model_name,
            horizon=effective_horizon,
            start_index=start_index if is_backtest else None,
            status="success",
            duration_ms=duration_ms,
            completed_at=datetime.utcnow().isoformat(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        fc_result = ForecastResult(
            task_id=task.id,
            dataset_id=dataset_id,
            forecasts=json.dumps(result["forecasts"], ensure_ascii=False),
            quantiles=json.dumps(result.get("quantiles", {}), ensure_ascii=False),
            future_times=json.dumps(future_times, ensure_ascii=False),
            actuals=json.dumps(actual_values, ensure_ascii=False),
            metrics=json.dumps(metrics, ensure_ascii=False),
            model_name=model_name,
            analysis=f"统计模型 {model_name} 预测完成。{preprocess_info['missing_filled']}个缺失值已填充，{preprocess_info['outliers_fixed']}个异常值已截断。",
        )
        db.add(fc_result)
        db.commit()
        db.refresh(fc_result)

        return {
            "task": _task_to_out(task),
            "result": _result_to_out(fc_result),
        }

    except Exception as e:
        if isinstance(e, APIError):
            raise
        raise APIError(f"统计模型预测失败: {e}", status_code=500)


# ==================== 导出增强（P3-4） ====================

def get_result_for_export_enhanced(db: Session, task_id: int) -> dict:
    """获取预测结果用于导出（增强版，含扩展指标+基线对比）"""
    data = get_result_for_export(db, task_id)
    # data 已含 forecasts/future_times/quantiles/actuals/metrics/start_index
    # metrics 中现在包含扩展指标和 baselines，直接透传
    return data
