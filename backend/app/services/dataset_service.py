"""数据集管理服务"""
import json

from sqlalchemy.orm import Session

from app.models import Dataset, ForecastTask, ForecastResult
from app.utils.response import APIError


def _to_out(ds: Dataset, include_data: bool = False) -> dict:
    """转输出格式"""
    out = {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description or "",
        "frequency": ds.frequency,
        "unit": ds.unit or "",
        "point_count": ds.point_count,
        "source": ds.source,
        "source_file": ds.source_file or "",
        "created_at": ds.created_at,
        "updated_at": ds.updated_at,
    }
    if include_data:
        out["series_data"] = _load_series(ds.series_data)
    return out


def _load_series(raw: str) -> list:
    """安全解析 series_data JSON"""
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _dump_series(data: list) -> str:
    """序列化 series_data 为 JSON 字符串"""
    return json.dumps(data, ensure_ascii=False)


def get_list(db: Session, keyword: str = None, frequency: str = None,
             page: int = 1, page_size: int = 20) -> dict:
    """获取数据集列表（分页）"""
    q = db.query(Dataset)
    if keyword:
        q = q.filter(Dataset.name.like(f"%{keyword}%"))
    if frequency:
        q = q.filter(Dataset.frequency == frequency)
    q = q.order_by(Dataset.id.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_to_out(d) for d in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_by_id(db: Session, id: int, include_data: bool = True) -> Dataset:
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    return ds


def get_detail(db: Session, id: int) -> dict:
    """获取数据集详情（含 series_data）"""
    ds = get_by_id(db, id)
    return _to_out(ds, include_data=True)


def create(db: Session, data: dict) -> dict:
    """手动创建数据集"""
    name = (data.get("name") or "").strip()
    if not name:
        raise APIError("数据集名称不能为空", status_code=400)
    series_data = data.get("series_data") or []
    if len(series_data) < 3:
        raise APIError(f"数据点数 {len(series_data)} 不足，至少需要 3 个", status_code=400)

    ds = Dataset(
        name=name,
        description=data.get("description", ""),
        frequency=data.get("frequency", "other"),
        unit=data.get("unit", ""),
        series_data=_dump_series(series_data),
        point_count=len(series_data),
        source=data.get("source", "manual"),
        source_file=data.get("source_file", ""),
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return _to_out(ds, include_data=True)


def update(db: Session, id: int, data: dict) -> dict:
    """更新数据集（元信息 + 可选 series_data）"""
    ds = get_by_id(db, id)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise APIError("数据集名称不能为空", status_code=400)
        ds.name = name
    if "description" in data:
        ds.description = data.get("description", "")
    if "frequency" in data:
        ds.frequency = data.get("frequency", "other")
    if "unit" in data:
        ds.unit = data.get("unit", "")
    if "series_data" in data:
        series_data = data.get("series_data") or []
        if len(series_data) < 3:
            raise APIError(f"数据点数 {len(series_data)} 不足，至少需要 3 个", status_code=400)
        ds.series_data = _dump_series(series_data)
        ds.point_count = len(series_data)
    db.commit()
    db.refresh(ds)
    return _to_out(ds, include_data=True)


def delete(db: Session, id: int):
    """删除数据集（级联删除预测任务和结果）"""
    ds = get_by_id(db, id)
    # 先删除关联结果（ForecastResult 不通过 ORM cascade 自动清理 task 外键）
    db.query(ForecastResult).filter(ForecastResult.dataset_id == id).delete()
    db.query(ForecastTask).filter(ForecastTask.dataset_id == id).delete()
    db.delete(ds)
    db.commit()


def preview(db: Session, id: int, limit: int = 50) -> dict:
    """预览数据集（前 N 个点 + 基本统计）"""
    ds = get_by_id(db, id)
    series = _load_series(ds.series_data)
    values = [p.get("value", 0) for p in series if p.get("value") is not None]
    stats = {}
    if values:
        stats = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": round(sum(values) / len(values), 2),
            "first": values[0],
            "last": values[-1],
        }
    return {
        "dataset": _to_out(ds),
        "points": series[:limit],
        "stats": stats,
    }


def import_from_excel(db: Session, file_bytes: bytes, filename: str,
                      name: str = None, frequency: str = "other",
                      unit: str = "", description: str = "") -> dict:
    """从 Excel/CSV 导入数据集（根据扩展名自动选择解析器）"""
    from app.utils.excel_parser import parse_file
    result = parse_file(file_bytes, filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "excel"
    ds_name = name or filename.rsplit(".", 1)[0]
    ds = Dataset(
        name=ds_name,
        description=description,
        frequency=frequency,
        unit=unit,
        series_data=_dump_series(result["series_data"]),
        point_count=result["point_count"],
        source="csv" if ext == "csv" else "excel",
        source_file=filename,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return {
        "dataset": _to_out(ds, include_data=True),
        "warnings": result["warnings"],
    }
