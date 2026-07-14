"""会话管理服务"""
import json
import logging
from typing import Optional, List

from app.models import Conversation, ConversationMessage, KnowledgeBase
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.utils.response import APIError

logger = logging.getLogger(__name__)


def _to_out(conv: Conversation, include_messages: bool = False) -> dict:
    """转输出格式"""
    kb_ids = [kb.id for kb in conv.knowledge_bases]
    kb_names = [kb.name for kb in conv.knowledge_bases]
    out = {
        "id": conv.id,
        "title": conv.title,
        "description": conv.description or "",
        "knowledge_base_ids": kb_ids,
        "knowledge_base_names": kb_names,
        "message_count": len(conv.messages) if conv.messages else 0,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }
    if include_messages:
        out["messages"] = [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json) if m.sources_json else [],
                "token_input": m.token_input,
                "token_output": m.token_output,
                "duration_ms": m.duration_ms,
                "model_name": m.model_name,
                "created_at": m.created_at,
            }
            for m in (conv.messages or [])
        ]
    return out


def get_list(db, keyword: Optional[str] = None, page: int = 1, page_size: int = 20):
    """会话分页列表"""
    q = db.query(Conversation)
    if keyword:
        q = q.filter(Conversation.title.like(f"%{keyword}%"))
    total = q.count()
    items = q.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_to_out(c) for c in items], total


def get_by_id(db, conv_id: int) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise APIError("会话不存在", status_code=404)
    return conv


def get_detail(db, conv_id: int) -> dict:
    """会话详情（含消息历史）"""
    conv = get_by_id(db, conv_id)
    return _to_out(conv, include_messages=True)


def create(db, data: ConversationCreate) -> Conversation:
    """创建会话"""
    conv = Conversation(
        title=data.title,
        description=data.description,
    )
    # 关联知识库
    if data.knowledge_base_ids:
        kbs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(data.knowledge_base_ids)).all()
        conv.knowledge_bases = kbs
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def update(db, conv_id: int, data: ConversationUpdate) -> Conversation:
    """更新会话"""
    conv = get_by_id(db, conv_id)
    if data.title is not None:
        conv.title = data.title
    if data.description is not None:
        conv.description = data.description
    if data.knowledge_base_ids is not None:
        kbs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(data.knowledge_base_ids)).all()
        conv.knowledge_bases = kbs
    db.commit()
    db.refresh(conv)
    return conv


def delete(db, conv_id: int):
    """删除会话（消息级联删除）"""
    conv = get_by_id(db, conv_id)
    db.delete(conv)
    db.commit()


def add_message(db, conv_id: int, role: str, content: str, sources: list = None,
                token_input: int = 0, token_output: int = 0,
                duration_ms: int = 0, model_name: str = None) -> ConversationMessage:
    """添加一条消息到会话"""
    msg = ConversationMessage(
        conversation_id=conv_id,
        role=role,
        content=content,
        sources_json=json.dumps(sources or [], ensure_ascii=False),
        token_input=token_input,
        token_output=token_output,
        duration_ms=duration_ms,
        model_name=model_name,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_history(db, conv_id: int, turns: int = 6) -> list:
    """获取最近 N 轮对话历史（用于上下文）

    Returns:
        list[dict]: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    """
    msgs = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conv_id)
        .order_by(ConversationMessage.id.desc())
        .limit(turns * 2)  # 每轮包含 user + assistant
        .all()
    )
    msgs.reverse()  # 恢复时间顺序
    return [{"role": m.role, "content": m.content} for m in msgs]


def get_kb_ids(db, conv_id: int) -> List[int]:
    """获取会话关联的知识库 ID 列表"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        return []
    return [kb.id for kb in conv.knowledge_bases]
