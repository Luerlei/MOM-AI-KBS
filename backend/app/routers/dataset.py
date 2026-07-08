"""数据集管理路由"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
import io
from urllib.parse import quote
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import dataset_service
from app.utils.response import success, page_result, APIError

router = APIRouter()


def _content_disposition(filename: str) -> str:
    """生成兼容非 ASCII 文件名的 Content-Disposition 头（RFC 5987）"""
    return f"attachment; filename=\"{quote(filename)}\"; filename*=UTF-8''{quote(filename)}"


@router.get("")
def list_datasets(
    keyword: str = Query(None),
    frequency: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """数据集列表（分页）"""
    result = dataset_service.get_list(db, keyword=keyword, frequency=frequency,
                                       page=page, page_size=page_size)
    return page_result(result["items"], result["total"], result["page"], result["page_size"])


@router.get("/template")
def download_template(format: str = "excel"):
    """下载导入模板（excel 或 csv）"""
    from app.utils.excel_parser import generate_template, generate_csv_template
    if format == "csv":
        content = generate_csv_template()
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=dataset-template.csv"},
        )
    else:
        content = generate_template()
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=dataset-template.xlsx"},
        )


@router.post("/import")
async def import_dataset(
    file: UploadFile = File(...),
    name: str = Form(""),
    frequency: str = Form("other"),
    unit: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    """导入数据集（支持 .xlsx / .xls / .csv）"""
    if not file.filename:
        raise APIError("未提供文件", status_code=400)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("xlsx", "xls", "csv"):
        raise APIError("仅支持 .xlsx / .xls / .csv 格式", status_code=400)

    file_bytes = await file.read()
    result = dataset_service.import_from_excel(
        db, file_bytes, file.filename,
        name=name or None, frequency=frequency, unit=unit, description=description,
    )
    return success(result, message=f"导入成功，共 {result['dataset']['point_count']} 个数据点")


@router.get("/{dataset_id}/export")
def export_dataset(
    dataset_id: int,
    format: str = "excel",
    with_forecast: bool = False,
    db: Session = Depends(get_db),
):
    """导出数据集（支持 excel / csv，可选含预测结果）"""
    from app.utils.excel_parser import export_dataset_excel, export_dataset_csv
    from app.services.forecast_service import get_latest_result

    detail = dataset_service.get_detail(db, dataset_id)
    series_data = detail["series_data"]

    forecasts, future_times, quantiles = None, None, None
    if with_forecast:
        latest = get_latest_result(db, dataset_id)
        if latest:
            r = latest["result"]
            forecasts = r["forecasts"]
            future_times = r["future_times"]
            quantiles = r["quantiles"]

    safe_name = detail["name"].replace("/", "-").replace("\\", "-")

    if format == "csv":
        content = export_dataset_csv(
            detail["name"], detail["frequency"], detail["unit"], series_data,
            forecasts, future_times, quantiles,
        )
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={"Content-Disposition": _content_disposition(f"{safe_name}.csv")},
        )
    else:
        content = export_dataset_excel(
            detail["name"], detail["frequency"], detail["unit"], series_data,
            forecasts, future_times, quantiles,
        )
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": _content_disposition(f"{safe_name}.xlsx")},
        )


@router.get("/{dataset_id}/preview")
def preview_dataset(dataset_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """预览数据集（前 N 个点 + 统计）"""
    return success(dataset_service.preview(db, dataset_id, limit=limit))


@router.get("/{dataset_id}")
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """数据集详情"""
    return success(dataset_service.get_detail(db, dataset_id))


@router.post("")
def create_dataset(data: dict, db: Session = Depends(get_db)):
    """手动创建数据集"""
    return success(dataset_service.create(db, data), message="创建成功")


@router.put("/{dataset_id}")
def update_dataset(dataset_id: int, data: dict, db: Session = Depends(get_db)):
    """更新数据集"""
    return success(dataset_service.update(db, dataset_id, data), message="更新成功")


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """删除数据集（级联删除预测任务和结果）"""
    dataset_service.delete(db, dataset_id)
    return success(message="删除成功")
