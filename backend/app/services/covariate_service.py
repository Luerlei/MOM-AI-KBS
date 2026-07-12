"""协变量服务

负责协变量的 CRUD、自动生成、时间对齐和 exog 矩阵构建。

核心函数:
- list_covariates / create_covariate / update_covariate / delete_covariate
- auto_generate_covariates  自动生成工作日/节假日/趋势/周期协变量
- build_exog_matrix          构建 exog 矩阵（供 ARIMA 等模型使用）
- align_covariate            协变量时间轴与主数据时间轴对齐
"""
import json
import math
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from app.models import Dataset, DatasetCovariate
from app.services.dataset_service import _load_series
from app.utils.response import APIError


# ==================== 查询 ====================

def list_covariates(db: Session, dataset_id: int) -> List[dict]:
    """列出数据集的所有协变量"""
    items = (
        db.query(DatasetCovariate)
        .filter(DatasetCovariate.dataset_id == dataset_id)
        .order_by(DatasetCovariate.id.asc())
        .all()
    )
    return [_to_out(c) for c in items]


def get_covariate(db: Session, covariate_id: int) -> DatasetCovariate:
    c = db.query(DatasetCovariate).filter(DatasetCovariate.id == covariate_id).first()
    if not c:
        raise APIError("协变量不存在", status_code=404)
    return c


# ==================== 增删改 ====================

def create_covariate(db: Session, dataset_id: int, name: str, code: str,
                     cov_type: str = "continuous", values: list = None,
                     description: str = "", source_type: str = "manual") -> dict:
    """新增协变量

    Args:
        values: [{time, value}, ...] 列表
        code: 英文标识，同一 dataset_id 下唯一
    """
    # 校验数据集存在
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)

    # 校验 code 唯一
    existing = (
        db.query(DatasetCovariate)
        .filter(DatasetCovariate.dataset_id == dataset_id,
                DatasetCovariate.code == code)
        .first()
    )
    if existing:
        raise APIError(f"协变量标识 '{code}' 已存在", status_code=400)

    c = DatasetCovariate(
        dataset_id=dataset_id,
        name=name,
        code=code,
        type=cov_type,
        source_type=source_type,
        values_json=json.dumps(values or [], ensure_ascii=False),
        description=description,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)


def update_covariate(db: Session, covariate_id: int, **kwargs) -> dict:
    """修改协变量"""
    c = get_covariate(db, covariate_id)

    if "name" in kwargs:
        c.name = kwargs["name"]
    if "code" in kwargs:
        # code 唯一性校验
        if kwargs["code"] != c.code:
            existing = (
                db.query(DatasetCovariate)
                .filter(DatasetCovariate.dataset_id == c.dataset_id,
                        DatasetCovariate.code == kwargs["code"])
                .first()
            )
            if existing:
                raise APIError(f"协变量标识 '{kwargs['code']}' 已存在", status_code=400)
            c.code = kwargs["code"]
    if "type" in kwargs:
        c.type = kwargs["type"]
    if "description" in kwargs:
        c.description = kwargs["description"]
    if "values" in kwargs:
        c.values_json = json.dumps(kwargs["values"] or [], ensure_ascii=False)

    db.commit()
    db.refresh(c)
    return _to_out(c)


def delete_covariate(db: Session, covariate_id: int) -> None:
    """删除协变量"""
    c = get_covariate(db, covariate_id)
    db.delete(c)
    db.commit()


# ==================== 自动生成 ====================

def auto_generate_covariates(db: Session, dataset_id: int,
                              skip_existing: bool = True) -> dict:
    """自动生成通用协变量（工作日/节假日/趋势/周期）

    根据 frequency 生成合适的协变量:
    - daily: 工作日 + 节假日 + 趋势 + 星期周期
    - weekly: 节假日 + 趋势 + 月度周期
    - monthly: 节假日(月内) + 趋势 + 月份周期
    - quarterly/yearly: 趋势 + 月份周期
    - hourly: 工作日 + 节假日 + 小时周期 + 趋势

    Args:
        skip_existing: True 时已存在的 auto 类型协变量跳过；False 时覆盖
    """
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)

    series = _load_series(ds.series_data)
    if not series:
        raise APIError("数据集为空", status_code=400)

    times = [p.get("time", "") for p in series]
    frequency = ds.frequency or "other"

    generated = []
    skipped = []

    # 已存在的 auto 协变量 code 集合
    existing_auto_codes = set()
    if skip_existing:
        existing = (
            db.query(DatasetCovariate)
            .filter(DatasetCovariate.dataset_id == dataset_id,
                    DatasetCovariate.source_type == "auto")
            .all()
        )
        existing_auto_codes = {c.code for c in existing}

    def _add(code: str, name: str, cov_type: str, values: list, desc: str):
        if skip_existing and code in existing_auto_codes:
            skipped.append(code)
            return
        # 覆盖已有 auto 协变量
        existing_c = (
            db.query(DatasetCovariate)
            .filter(DatasetCovariate.dataset_id == dataset_id,
                    DatasetCovariate.code == code)
            .first()
        )
        if existing_c:
            existing_c.name = name
            existing_c.type = cov_type
            existing_c.values_json = json.dumps(values, ensure_ascii=False)
            existing_c.description = desc
            generated.append(code)
        else:
            c = DatasetCovariate(
                dataset_id=dataset_id,
                name=name,
                code=code,
                type=cov_type,
                source_type="auto",
                values_json=json.dumps(values, ensure_ascii=False),
                description=desc,
            )
            db.add(c)
            generated.append(code)

    # 1. 趋势项（所有频率都生成）
    trend_values = [{"time": t, "value": float(i + 1)} for i, t in enumerate(times)]
    _add("trend", "趋势项", "continuous", trend_values, "线性趋势 t=1,2,3...")

    # 2. 节假日（daily/weekly/monthly 生成）
    if frequency in ("daily", "weekly", "monthly"):
        holidays = _load_china_holidays()
        holiday_values = []
        for t in times:
            dt = _parse_date(t)
            is_holiday = 0
            if dt and dt.strftime("%Y-%m-%d") in holidays:
                is_holiday = 1
            # monthly: 当月内是否有节假日
            if frequency == "monthly" and dt:
                year_month = dt.strftime("%Y-%m")
                is_holiday = 1 if any(h.startswith(year_month) for h in holidays) else 0
            holiday_values.append({"time": t, "value": float(is_holiday)})
        _add("is_holiday", "节假日", "binary", holiday_values,
             "中国法定节假日（1=节假日，0=非节假日）")

    # 3. 工作日（daily/hourly 生成）
    if frequency in ("daily", "hourly"):
        weekend_values = []
        for t in times:
            dt = _parse_date(t)
            is_weekend = 0
            if dt and dt.weekday() >= 5:
                is_weekend = 1
            weekend_values.append({"time": t, "value": float(is_weekend)})
        _add("is_weekend", "周末", "binary", weekend_values,
             "是否周末（1=周六/周日，0=工作日）")

    # 4. 周期特征
    if frequency == "monthly":
        month_sin_values = []
        month_cos_values = []
        for t in times:
            dt = _parse_date(t)
            if dt:
                m = dt.month
            else:
                # 尝试从字符串提取月份数字
                m = _extract_month_from_string(t) or 1
            month_sin_values.append({"time": t, "value": round(math.sin(2 * math.pi * m / 12), 4)})
            month_cos_values.append({"time": t, "value": round(math.cos(2 * math.pi * m / 12), 4)})
        _add("month_sin", "月份正弦", "continuous", month_sin_values,
             "月份的 sin 编码（捕捉年度季节性）")
        _add("month_cos", "月份余弦", "continuous", month_cos_values,
             "月份的 cos 编码（捕捉年度季节性）")

    elif frequency == "daily":
        dow_sin_values = []
        dow_cos_values = []
        for t in times:
            dt = _parse_date(t)
            dow = dt.weekday() if dt else 0
            dow_sin_values.append({"time": t, "value": round(math.sin(2 * math.pi * dow / 7), 4)})
            dow_cos_values.append({"time": t, "value": round(math.cos(2 * math.pi * dow / 7), 4)})
        _add("dow_sin", "星期正弦", "continuous", dow_sin_values,
             "星期的 sin 编码（捕捉周季节性）")
        _add("dow_cos", "星期余弦", "continuous", dow_cos_values,
             "星期的 cos 编码（捕捉周季节性）")

    elif frequency == "quarterly":
        q_sin_values = []
        q_cos_values = []
        for t in times:
            dt = _parse_date(t)
            if dt:
                q = (dt.month - 1) // 3 + 1
            else:
                q = _extract_quarter_from_string(t) or 1
            q_sin_values.append({"time": t, "value": round(math.sin(2 * math.pi * q / 4), 4)})
            q_cos_values.append({"time": t, "value": round(math.cos(2 * math.pi * q / 4), 4)})
        _add("quarter_sin", "季度正弦", "continuous", q_sin_values,
             "季度的 sin 编码（捕捉年度季节性）")
        _add("quarter_cos", "季度余弦", "continuous", q_cos_values,
             "季度的 cos 编码（捕捉年度季节性）")

    db.commit()
    return {
        "generated": generated,
        "skipped": skipped,
        "total": len(generated),
    }


# ==================== exog 矩阵构建 ====================

def build_exog_matrix(db: Session, dataset_id: int,
                      train_times: list, future_times: Optional[list] = None) -> Tuple[
    Optional[np.ndarray], Optional[np.ndarray], List[str]]:
    """构建 exog 矩阵（供 ARIMA 等模型使用）

    Args:
        dataset_id: 数据集 ID
        train_times: 训练数据的时间标签列表
        future_times: 未来预测点的时间标签列表（None 则不构建未来矩阵）

    Returns:
        (X_train, X_future, feature_names)
        - X_train: shape [n_train, n_features]，无协变量时返回 None
        - X_future: shape [horizon, n_features]，无 future_times 或无协变量时返回 None
        - feature_names: 协变量 code 列表
    """
    covariates = (
        db.query(DatasetCovariate)
        .filter(DatasetCovariate.dataset_id == dataset_id)
        .order_by(DatasetCovariate.id.asc())
        .all()
    )
    if not covariates:
        return None, None, []

    feature_names = [c.code for c in covariates]

    # 构建 train 矩阵
    X_train_cols = []
    for cov in covariates:
        cov_values = json.loads(cov.values_json) if cov.values_json else []
        aligned = align_covariate(train_times, cov_values)
        X_train_cols.append(aligned)
    X_train = np.array(X_train_cols).T if X_train_cols else None  # [n_train, n_features]

    # 构建 future 矩阵
    X_future = None
    if future_times:
        X_future_cols = []
        for cov in covariates:
            cov_values = json.loads(cov.values_json) if cov.values_json else []
            aligned = align_covariate(future_times, cov_values)
            X_future_cols.append(aligned)
        X_future = np.array(X_future_cols).T if X_future_cols else None

    return X_train, X_future, feature_names


def align_covariate(main_times: list, cov_values: list) -> list:
    """协变量时间轴与主数据时间轴对齐

    匹配策略:
    1. 精确匹配 time 字段
    2. 日期前缀匹配（monthly: "2024-01" 匹配 "2024-01-15"）
    3. 缺失时填 0.0

    Args:
        main_times: 主数据时间标签列表
        cov_values: [{time, value}, ...]

    Returns:
        对齐后的 value 列表（长度 == len(main_times)）
    """
    # 构建协变量查找表
    cov_map = {}
    for item in cov_values:
        t = item.get("time", "")
        v = item.get("value", 0.0)
        try:
            v = float(v)
        except (ValueError, TypeError):
            v = 0.0
        cov_map[t] = v

    result = []
    for mt in main_times:
        # 1. 精确匹配
        if mt in cov_map:
            result.append(cov_map[mt])
            continue
        # 2. 日期前缀匹配（monthly/quarterly → daily 的场景）
        matched = False
        for ct, cv in cov_map.items():
            if ct and mt and len(ct) >= 7 and len(mt) >= 7:
                if ct[:7] == mt[:7]:  # "2024-01" 前缀
                    result.append(cv)
                    matched = True
                    break
        if matched:
            continue
        # 3. 缺失填 0
        result.append(0.0)
    return result


# ==================== 预览 ====================

def preview_covariates(db: Session, dataset_id: int) -> dict:
    """预览对齐后的协变量矩阵（与主数据时间轴对齐）"""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)

    series = _load_series(ds.series_data)
    times = [p.get("time", "") for p in series]
    values = [p.get("value", 0) for p in series]

    covariates = (
        db.query(DatasetCovariate)
        .filter(DatasetCovariate.dataset_id == dataset_id)
        .order_by(DatasetCovariate.id.asc())
        .all()
    )

    columns = [{"title": "时间", "key": "time"}, {"title": "主值", "key": "value"}]
    for c in covariates:
        columns.append({"title": c.name, "key": c.code})

    rows = []
    for i, t in enumerate(times):
        row = {"time": t, "value": values[i]}
        for c in covariates:
            cov_values = json.loads(c.values_json) if c.values_json else []
            aligned = align_covariate([t], cov_values)
            row[c.code] = aligned[0] if aligned else 0.0
        rows.append(row)

    return {
        "columns": columns,
        "rows": rows,
        "covariate_count": len(covariates),
        "point_count": len(times),
    }


# ==================== 内部工具 ====================

def _to_out(c: DatasetCovariate) -> dict:
    return {
        "id": c.id,
        "dataset_id": c.dataset_id,
        "name": c.name,
        "code": c.code,
        "type": c.type,
        "source_type": c.source_type,
        "values": json.loads(c.values_json) if c.values_json else [],
        "description": c.description or "",
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _load_china_holidays() -> set:
    """加载中国节假日日期集合"""
    holidays_path = os.path.join(os.path.dirname(__file__), "..", "data", "china_holidays.json")
    holidays_path = os.path.normpath(holidays_path)
    try:
        with open(holidays_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = set()
        for year, dates in data.items():
            for d in dates:
                result.add(d)
        return result
    except Exception:
        return set()


def _parse_date(s: str):
    """多格式日期解析"""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    # 常见格式
    formats = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%Y-%m", "%Y/%m/%d", "%Y/%m", "%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # 季度格式 "2024-Q1"
    import re
    m = re.match(r"(\d{4})-Q(\d)", s)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return datetime(y, (q - 1) * 3 + 1, 1)
    return None


def _extract_month_from_string(s: str) -> Optional[int]:
    """从字符串提取月份数字"""
    import re
    m = re.search(r"(\d{4})-(\d{1,2})", s)
    if m:
        return int(m.group(2))
    return None


def _extract_quarter_from_string(s: str) -> Optional[int]:
    """从字符串提取季度数字"""
    import re
    m = re.search(r"Q(\d)", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None
