"""知识库管理服务"""
import logging
from typing import Optional

from app.models import KnowledgeBase, Knowledge, ModelConfig
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.utils.response import APIError

logger = logging.getLogger(__name__)


def _to_out(kb: KnowledgeBase, doc_count: int = None) -> dict:
    """转输出格式"""
    out = {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description or "",
        "llm_config_id": kb.llm_config_id,
        "embedding_config_id": kb.embedding_config_id,
        "rerank_config_id": kb.rerank_config_id,
        "ocr_config_id": kb.ocr_config_id,
        "vlm_config_id": kb.vlm_config_id,
        "parse_on_upload": kb.parse_on_upload,
        # 关联模型名称
        "llm_model_name": kb.llm_config.model_name if kb.llm_config else None,
        "embedding_model_name": kb.embedding_config.model_name if kb.embedding_config else None,
        "rerank_model_name": kb.rerank_config.model_name if kb.rerank_config else None,
        "ocr_model_name": kb.ocr_config.model_name if kb.ocr_config else None,
        "vlm_model_name": kb.vlm_config.model_name if kb.vlm_config else None,
        "created_at": kb.created_at,
        "updated_at": kb.updated_at,
    }
    if doc_count is not None:
        out["document_count"] = doc_count
    else:
        out["document_count"] = 0
    return out


def get_list(db, keyword: Optional[str] = None, page: int = 1, page_size: int = 20):
    """知识库分页列表"""
    from sqlalchemy.orm import joinedload
    q = db.query(KnowledgeBase).options(
        joinedload(KnowledgeBase.llm_config),
        joinedload(KnowledgeBase.embedding_config),
        joinedload(KnowledgeBase.rerank_config),
        joinedload(KnowledgeBase.ocr_config),
        joinedload(KnowledgeBase.vlm_config),
    )
    if keyword:
        q = q.filter(KnowledgeBase.name.like(f"%{keyword}%"))
    total = q.count()
    items = q.order_by(KnowledgeBase.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # 批量查询文档数
    result = []
    for kb in items:
        doc_count = db.query(Knowledge).filter(Knowledge.knowledge_base_id == kb.id).count()
        result.append(_to_out(kb, doc_count))
    return result, total


def get_by_id(db, kb_id: int) -> KnowledgeBase:
    """按 ID 查询知识库（含关联配置）"""
    from sqlalchemy.orm import joinedload
    kb = (
        db.query(KnowledgeBase)
        .options(
            joinedload(KnowledgeBase.llm_config),
            joinedload(KnowledgeBase.embedding_config),
            joinedload(KnowledgeBase.rerank_config),
            joinedload(KnowledgeBase.ocr_config),
            joinedload(KnowledgeBase.vlm_config),
        )
        .filter(KnowledgeBase.id == kb_id)
        .first()
    )
    if not kb:
        raise APIError("知识库不存在", status_code=404)
    return kb


def get_detail(db, kb_id: int) -> dict:
    """知识库详情（含文档数）"""
    kb = get_by_id(db, kb_id)
    doc_count = db.query(Knowledge).filter(Knowledge.knowledge_base_id == kb_id).count()
    return _to_out(kb, doc_count)


def create(db, data: KnowledgeBaseCreate) -> KnowledgeBase:
    """创建知识库"""
    # 校验模型配置 ID 是否存在
    _validate_model_ids(db, data)
    kb = KnowledgeBase(
        name=data.name,
        description=data.description,
        llm_config_id=data.llm_config_id,
        embedding_config_id=data.embedding_config_id,
        rerank_config_id=data.rerank_config_id,
        ocr_config_id=data.ocr_config_id,
        vlm_config_id=data.vlm_config_id,
        parse_on_upload=data.parse_on_upload,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def update(db, kb_id: int, data: KnowledgeBaseUpdate) -> KnowledgeBase:
    """更新知识库"""
    kb = get_by_id(db, kb_id)
    # 校验模型配置 ID
    _validate_model_ids(db, data)
    if data.name is not None:
        kb.name = data.name
    if data.description is not None:
        kb.description = data.description
    if data.llm_config_id is not None:
        kb.llm_config_id = data.llm_config_id
    if data.embedding_config_id is not None:
        kb.embedding_config_id = data.embedding_config_id
    if data.rerank_config_id is not None:
        kb.rerank_config_id = data.rerank_config_id
    if data.ocr_config_id is not None:
        kb.ocr_config_id = data.ocr_config_id
    if data.vlm_config_id is not None:
        kb.vlm_config_id = data.vlm_config_id
    if data.parse_on_upload is not None:
        kb.parse_on_upload = data.parse_on_upload
    db.commit()
    db.refresh(kb)
    return kb


def delete(db, kb_id: int):
    """删除知识库（关联的 Knowledge 解除归属，不级联删除）"""
    kb = get_by_id(db, kb_id)
    # 解除关联的知识条目（knowledge_base_id 置 NULL，知识条目保留）
    db.query(Knowledge).filter(Knowledge.knowledge_base_id == kb_id).update(
        {Knowledge.knowledge_base_id: None}
    )
    db.delete(kb)
    db.commit()


def _validate_model_ids(db, data):
    """校验模型配置 ID 是否存在（不存在则报错）"""
    config_ids = []
    for attr in ("llm_config_id", "embedding_config_id", "rerank_config_id", "ocr_config_id", "vlm_config_id"):
        val = getattr(data, attr, None)
        if val is not None:
            config_ids.append((attr, val))
    if not config_ids:
        return
    for attr, cid in config_ids:
        exists = db.query(ModelConfig).filter(ModelConfig.id == cid).first()
        if not exists:
            raise APIError(f"模型配置不存在: {attr}={cid}", status_code=400)


def get_model_config_id(db, kb_id: int, model_type: str) -> Optional[int]:
    """获取知识库的指定类型模型配置 ID（为空返回 None，调用方继承全局）

    Args:
        model_type: LLM / Embedding / Rerank / OCR / VLM
    """
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        return None
    field_map = {
        "LLM": kb.llm_config_id,
        "Embedding": kb.embedding_config_id,
        "Rerank": kb.rerank_config_id,
        "OCR": kb.ocr_config_id,
        "VLM": kb.vlm_config_id,
    }
    return field_map.get(model_type)
