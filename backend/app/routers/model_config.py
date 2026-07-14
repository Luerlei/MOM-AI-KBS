"""模型配置路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModelConfig
from app.schemas.model_config import ModelConfigCreate, ModelConfigUpdate
from app.services import model_service
from app.utils.auth import require_auth
from app.utils.response import success, APIError

router = APIRouter()


@router.get("")
def list_models(type: str = None, db: Session = Depends(get_db), user=Depends(require_auth)):
    """模型配置列表（api_key 脱敏）"""
    items = model_service.get_list(db, type=type)
    return success(items)


@router.get("/status")
def get_status(db: Session = Depends(get_db), user=Depends(require_auth)):
    """获取当前启用的 LLM / Embedding / Forecast / Rerank / OCR / VLM 模型状态"""
    llm = db.query(ModelConfig).filter(ModelConfig.type == "LLM", ModelConfig.is_active == True).first()  # noqa: E712
    emb = db.query(ModelConfig).filter(ModelConfig.type == "Embedding", ModelConfig.is_active == True).first()  # noqa: E712
    fc = db.query(ModelConfig).filter(ModelConfig.type == "Forecast", ModelConfig.is_active == True).first()  # noqa: E712
    rr = db.query(ModelConfig).filter(ModelConfig.type == "Rerank", ModelConfig.is_active == True).first()  # noqa: E712
    ocr = db.query(ModelConfig).filter(ModelConfig.type == "OCR", ModelConfig.is_active == True).first()  # noqa: E712
    vlm = db.query(ModelConfig).filter(ModelConfig.type == "VLM", ModelConfig.is_active == True).first()  # noqa: E712

    embedding_status = None
    if emb:
        embedding_status = {"id": emb.id, "name": emb.name, "model_name": emb.model_name, "source": "external"}

    forecast_status = None
    if fc:
        forecast_status = {"id": fc.id, "name": fc.name, "model_name": fc.model_name, "source": "external"}

    rerank_status = None
    if rr:
        rerank_status = {"id": rr.id, "name": rr.name, "model_name": rr.model_name, "source": "external"}

    ocr_status = None
    if ocr:
        ocr_status = {"id": ocr.id, "name": ocr.name, "model_name": ocr.model_name, "source": "external"}

    vlm_status = None
    if vlm:
        vlm_status = {"id": vlm.id, "name": vlm.name, "model_name": vlm.model_name, "source": "external"}

    return success({
        "llm": {"id": llm.id, "name": llm.name, "model_name": llm.model_name} if llm else None,
        "embedding": embedding_status,
        "forecast": forecast_status,
        "rerank": rerank_status,
        "ocr": ocr_status,
        "vlm": vlm_status,
    })


@router.get("/{mid}")
def get_model(mid: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """模型详情"""
    c = model_service.get_by_id(db, mid)
    return success(model_service._to_out(c))


@router.post("")
def create_model(data: ModelConfigCreate, db: Session = Depends(get_db), user=Depends(require_auth)):
    """新增模型配置"""
    c = model_service.create(db, data)
    return success(model_service._to_out(c), message="创建成功")


@router.put("/{mid}")
def update_model(mid: int, data: ModelConfigUpdate, db: Session = Depends(get_db), user=Depends(require_auth)):
    """更新模型配置"""
    c = model_service.update(db, mid, data)
    return success(model_service._to_out(c), message="更新成功")


@router.delete("/{mid}")
def delete_model(mid: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """删除模型配置"""
    model_service.delete(db, mid)
    return success(message="删除成功")


@router.put("/{mid}/activate")
def activate_model(mid: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """启用模型"""
    c = model_service.activate(db, mid)
    return success(model_service._to_out(c), message="启用成功")


@router.post("/{mid}/test")
async def test_model(mid: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """测试连通性"""
    result = await model_service.test_connection(db, mid)
    return success({
        "success": result.success,
        "message": result.message,
        "latency_ms": result.latency_ms,
    })
