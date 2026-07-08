"""时序预测路由"""
import io
from urllib.parse import quote
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import forecast_service
from app.utils.response import success, page_result, APIError

router = APIRouter()


def _content_disposition(filename: str) -> str:
    """生成兼容非 ASCII 文件名的 Content-Disposition 头（RFC 5987）"""
    return f"attachment; filename=\"{quote(filename)}\"; filename*=UTF-8''{quote(filename)}"


@router.post("/predict")
async def predict(data: dict, db: Session = Depends(get_db)):
    """执行预测

    Body: {dataset_id: int, horizon: int, quantiles?: [float], start_index?: int, skip_analysis?: bool}
    start_index 设置时进入回测模式：用前 start_index 个点训练，预测后与实际值对照
    skip_analysis=true 时跳过 LLM 分析报告（节省 ~20s），仅用模板摘要
    """
    dataset_id = data.get("dataset_id")
    if not dataset_id:
        raise APIError("dataset_id 不能为空", status_code=400)
    horizon = data.get("horizon", 12)
    if not isinstance(horizon, int) or horizon <= 0:
        raise APIError("horizon 必须为正整数", status_code=400)
    quantiles = data.get("quantiles")
    start_index = data.get("start_index")  # None = 未来预测模式
    skip_analysis = bool(data.get("skip_analysis", False))

    result = await forecast_service.run_forecast(
        db, dataset_id=dataset_id, horizon=horizon,
        quantiles=quantiles, start_index=start_index,
        skip_analysis=skip_analysis,
    )
    return success(result, message="预测完成")


@router.get("/tasks")
def list_tasks(
    dataset_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """预测任务历史列表"""
    result = forecast_service.get_tasks(db, dataset_id=dataset_id, page=page, page_size=page_size)
    return page_result(result["items"], result["total"], result["page"], result["page_size"])


@router.get("/results/{dataset_id}")
def get_latest_result_api(dataset_id: int, db: Session = Depends(get_db)):
    """获取数据集最新预测结果"""
    result = forecast_service.get_latest_result(db, dataset_id)
    return success(result)


@router.get("/trend/{dataset_id}")
def get_trend_analysis(dataset_id: int, db: Session = Depends(get_db)):
    """获取趋势分析聚合数据（历史 + 最新预测 + 统计分析）"""
    result = forecast_service.get_trend_analysis(db, dataset_id)
    return success(result)


@router.get("/export/{task_id}")
def export_forecast_result(task_id: int, format: str = "excel", db: Session = Depends(get_db)):
    """导出预测结果（含原始数据 + 预测数据）"""
    from app.utils.excel_parser import export_dataset_excel, export_dataset_csv

    data = forecast_service.get_result_for_export(db, task_id)
    safe_name = (data["dataset_name"] or "forecast").replace("/", "-").replace("\\", "-")

    if format == "csv":
        content = export_dataset_csv(
            data["dataset_name"], data["frequency"], data["unit"], data["series_data"],
            data["forecasts"], data["future_times"], data["quantiles"],
            data.get("actuals"), data.get("metrics"),
        )
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={"Content-Disposition": _content_disposition(f"{safe_name}-forecast.csv")},
        )
    else:
        content = export_dataset_excel(
            data["dataset_name"], data["frequency"], data["unit"], data["series_data"],
            data["forecasts"], data["future_times"], data["quantiles"],
            data.get("actuals"), data.get("metrics"),
        )
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": _content_disposition(f"{safe_name}-forecast.xlsx")},
        )
