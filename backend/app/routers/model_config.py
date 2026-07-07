"""模型配置路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModelConfig
from app.schemas.model_config import ModelConfigCreate, ModelConfigUpdate
from app.services import model_service
from app.utils.response import success, APIError

router = APIRouter()


@router.get("")
def list_models(type: str = None, db: Session = Depends(get_db)):
    """模型配置列表（api_key 脱敏）"""
    items = model_service.get_list(db, type=type)
    return success(items)


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """获取当前启用的 LLM 和 Embedding 模型状态"""
    llm = db.query(ModelConfig).filter(ModelConfig.type == "LLM", ModelConfig.is_active == True).first()  # noqa: E712
    emb = db.query(ModelConfig).filter(ModelConfig.type == "Embedding", ModelConfig.is_active == True).first()  # noqa: E712

    embedding_status = None
    if emb:
        embedding_status = {"id": emb.id, "name": emb.name, "model_name": emb.model_name, "source": "external"}

    return success({
        "llm": {"id": llm.id, "name": llm.name, "model_name": llm.model_name} if llm else None,
        "embedding": embedding_status,
    })


@router.get("/{mid}")
def get_model(mid: int, db: Session = Depends(get_db)):
    """模型详情"""
    c = model_service.get_by_id(db, mid)
    return success(model_service._to_out(c))


@router.post("")
def create_model(data: ModelConfigCreate, db: Session = Depends(get_db)):
    """新增模型配置"""
    c = model_service.create(db, data)
    return success(model_service._to_out(c), message="创建成功")


@router.put("/{mid}")
def update_model(mid: int, data: ModelConfigUpdate, db: Session = Depends(get_db)):
    """更新模型配置"""
    c = model_service.update(db, mid, data)
    return success(model_service._to_out(c), message="更新成功")


@router.delete("/{mid}")
def delete_model(mid: int, db: Session = Depends(get_db)):
    """删除模型配置"""
    model_service.delete(db, mid)
    return success(message="删除成功")


@router.put("/{mid}/activate")
def activate_model(mid: int, db: Session = Depends(get_db)):
    """启用模型"""
    c = model_service.activate(db, mid)
    return success(model_service._to_out(c), message="启用成功")


@router.post("/{mid}/test")
async def test_model(mid: int, db: Session = Depends(get_db)):
    """测试连通性"""
    result = await model_service.test_connection(db, mid)
    return success({
        "success": result.success,
        "message": result.message,
        "latency_ms": result.latency_ms,
    })
