"""时序预测服务

包含：
- 预测执行（调用 ForecastClient + 存任务/结果）
- 未来时间标签生成（基于历史频率外推）
- 基础统计算法（趋势方向、强度、增长率、波动性）
- LLM 自然语言分析报告
- TokenUsage 日志记录
"""
import json
import math
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Dataset, ForecastTask, ForecastResult, TokenUsage, ModelConfig
from app.services.dataset_service import _load_series
from app.utils.response import APIError


# ==================== 预测执行 ====================

async def run_forecast(db: Session, dataset_id: int, horizon: int,
                       quantiles: list = None, start_index: int = None,
                       skip_analysis: bool = False) -> dict:
    """执行预测

    Args:
        start_index: 回测起点。若设置，则用前 start_index 个点作为训练数据预测，
                     与后续实际值对照。None 表示从末尾预测未来。
        skip_analysis: 跳过 LLM 分析报告生成（节省 ~20s），仅用模板摘要。

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

    # 回测模式：拆分训练数据和对照实际值
    is_backtest = start_index is not None and start_index < len(full_values)
    if is_backtest:
        if start_index < 3:
            raise APIError("回测起点至少需要 3 个训练点", status_code=400)
        # 训练数据
        values = full_values[:start_index]
        times = full_times[:start_index]
        # 实际对照值（限制不超过剩余点数）
        actual_count = min(horizon, len(full_values) - start_index)
        actual_values = full_values[start_index:start_index + actual_count]
        actual_times = full_times[start_index:start_index + actual_count]
        # 预测步数以实际对照数为准（避免多余预测）
        effective_horizon = actual_count
    else:
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

        # 7. 回测误差计算
        metrics = {}
        if is_backtest and actual_values:
            metrics = _compute_metrics(actual_values, result["forecasts"][:len(actual_values)])

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
    """获取预测任务历史"""
    q = db.query(ForecastTask)
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
    """获取数据集最新预测结果"""
    task = (
        db.query(ForecastTask)
        .filter(ForecastTask.dataset_id == dataset_id, ForecastTask.status == "success")
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

    # 平均环比增长率
    growth_rate = 0.0
    if n >= 2:
        rates = []
        for i in range(1, n):
            prev = values[i - 1]
            if abs(prev) > 1e-9:
                rates.append((values[i] - prev) / prev * 100)
        if rates:
            growth_rate = round(sum(rates) / len(rates), 2)

    # 变异系数（波动性）
    variance = sum((y - y_mean) ** 2 for y in values) / n
    std = math.sqrt(variance)
    volatility = round(std / avg * 100, 2) if abs(avg) > 1e-9 else 0.0

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


def _compute_metrics(actuals: list, forecasts: list) -> dict:
    """计算回测误差指标

    Returns:
        {
            "mae": 平均绝对误差,
            "mape": 平均绝对百分比误差 %,
            "rmse": 均方根误差,
            "max_error": 最大绝对误差,
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

    return {
        "mae": round(mae, 4),
        "mape": round(mape, 2),
        "rmse": round(rmse, 4),
        "max_error": round(max(abs_errors), 4),
    }


# ==================== LLM 自然语言分析 ====================

async def _generate_llm_analysis(ds_name: str, frequency: str, unit: str,
                                  times: list, values: list,
                                  forecasts: list, future_times: list,
                                  quantiles: dict, stats: dict,
                                  is_backtest: bool = False,
                                  actual_values: list = None,
                                  metrics: dict = None,
                                  db: Session = None) -> str:
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

    # 压缩历史数据（避免 token 过多）
    history_str = ", ".join(f"{t}:{v}" for t, v in zip(times[-12:], values[-12:]))
    forecast_str = ", ".join(f"{t}:{round(f, 2)}" for t, f in zip(future_times, forecasts))

    p10 = quantiles.get("0.1", [])
    p90 = quantiles.get("0.9", [])
    interval_str = ""
    if p10 and p90:
        interval_str = f"\n- 预测 10% 下界: {', '.join(str(round(x, 2)) for x in p10)}"
        interval_str += f"\n- 预测 90% 上界: {', '.join(str(round(x, 2)) for x in p90)}"

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
        backtest_section = f"""
## 回测对照结果
- 预测起点：前 {len(values)} 个点作为训练数据
- 实际值：{actual_str}
- 逐点对比：{compare_str}
- 误差指标：MAE={m.get('mae', 0)}{unit_text}, MAPE={m.get('mape', 0)}%, RMSE={m.get('rmse', 0)}{unit_text}, 最大误差={m.get('max_error', 0)}{unit_text}
"""
        backtest_requirements = """
5. **回测精度评估**：模型预测与实际值的偏差分析、哪几个点偏差最大及可能原因、模型适用性评价"""

    prompt = f"""你是时序数据分析专家。请基于以下数据生成简洁的中文趋势分析报告。

## 数据集信息
- 名称: {ds_name}
- 频率: {freq_text}
- 单位: {unit_text}

## 历史数据（最近12个点）
{history_str}

## 统计指标
- 数据点数: {stats.get('count', 0)}
- 最小值: {stats.get('min', 0)}, 最大值: {stats.get('max', 0)}, 均值: {stats.get('avg', 0)}
- 首值: {stats.get('first', 0)}, 末值: {stats.get('last', 0)}
- 趋势方向: {stats.get('trend_direction', 'unknown')}（R²={stats.get('trend_strength', 0)}）
- 平均环比增长率: {stats.get('growth_rate', 0)}%
- 波动性（变异系数）: {stats.get('volatility', 0)}%

## 预测结果（未来{len(forecasts)}步）
{forecast_str}{interval_str}
{backtest_section}
## 要求
请用 3-4 段话输出分析报告，包含：
1. **历史趋势概述**：数据整体走势、关键转折点
2. **波动性分析**：数据稳定性、异常点（如有 label 标注）
3. **预测解读**：预测值的含义、置信区间宽窄、可能的风险
4. **建议**：基于分析给出 1-2 条行动建议
{backtest_requirements}
直接输出报告正文，不要加标题和额外说明。"""

    messages = [
        {"role": "system", "content": "你是专业的时序数据分析专家，擅长用简洁中文撰写分析报告。"},
        {"role": "user", "content": prompt},
    ]

    try:
        llm_start = time.time()
        result = await llm.chat(messages)
        llm_duration = int((time.time() - llm_start) * 1000)
        content = result.get("content", "").strip()

        # 记录 LLM 调用的 TokenUsage 日志
        if db is not None:
            usage = getattr(llm, "last_usage", {}) or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            try:
                log = TokenUsage(
                    call_type="trend_analysis",
                    model_name=llm.model_name,
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
        return fallback
