"""协变量路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import covariate_service
from app.utils.response import success, APIError
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/datasets/{dataset_id}/covariates")
def list_covariates(dataset_id: int, db: Session = Depends(get_db)):
    """列出数据集的所有协变量"""
    items = covariate_service.list_covariates(db, dataset_id)
    return success(items)


@router.post("/datasets/{dataset_id}/covariates")
def create_covariate(dataset_id: int, data: dict, db: Session = Depends(get_db)):
    """新增协变量

    Body: {name, code, type?, values?, description?}
    """
    name = data.get("name", "").strip()
    code = data.get("code", "").strip()
    if not name or not code:
        raise APIError("name 和 code 不能为空", status_code=400)
    cov_type = data.get("type", "continuous")
    values = data.get("values", [])
    description = data.get("description", "")
    result = covariate_service.create_covariate(
        db, dataset_id=dataset_id, name=name, code=code,
        cov_type=cov_type, values=values, description=description,
    )
    return success(result, message="协变量创建成功")


@router.put("/covariates/{covariate_id}")
def update_covariate(covariate_id: int, data: dict, db: Session = Depends(get_db)):
    """修改协变量"""
    result = covariate_service.update_covariate(db, covariate_id, **data)
    return success(result, message="协变量更新成功")


@router.delete("/covariates/{covariate_id}")
def delete_covariate(covariate_id: int, db: Session = Depends(get_db)):
    """删除协变量"""
    covariate_service.delete_covariate(db, covariate_id)
    return success(None, message="协变量删除成功")


@router.post("/datasets/{dataset_id}/covariates/auto-generate")
def auto_generate(dataset_id: int, data: dict, db: Session = Depends(get_db)):
    """自动生成通用协变量

    Body: {skip_existing?: bool}
    """
    skip_existing = data.get("skip_existing", True)
    result = covariate_service.auto_generate_covariates(
        db, dataset_id, skip_existing=skip_existing,
    )
    return success(result, message=f"已生成 {result['total']} 个协变量")


@router.get("/datasets/{dataset_id}/covariates/preview")
def preview(dataset_id: int, db: Session = Depends(get_db)):
    """预览对齐后的协变量矩阵"""
    result = covariate_service.preview_covariates(db, dataset_id)
    return success(result)


@router.get("/datasets/{dataset_id}/covariates/future-times")
def get_future_times(dataset_id: int, horizon: int = Query(6, ge=1, le=60), db: Session = Depends(get_db)):
    """根据数据集频率生成未来时间标签（用于协变量未来值录入辅助）

    Query: horizon=未来步数（1-60）
    """
    from app.services.forecast_service import _generate_future_times
    from app.services.dataset_service import _load_series
    from app.models import Dataset

    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise APIError("数据集不存在", status_code=404)
    series = _load_series(ds.series_data)
    history_times = [p.get("time", "") for p in series]
    future = _generate_future_times(history_times, horizon, ds.frequency)
    return success({"future_times": future, "frequency": ds.frequency})
