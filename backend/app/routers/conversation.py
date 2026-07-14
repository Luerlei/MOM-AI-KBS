"""会话管理路由"""
import json
import time
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Skill
from app.schemas.conversation import ConversationCreate, ConversationUpdate, ConversationAsk
from app.services import conversation_service
from app.services.rag_service import rag_service
from app.utils.auth import require_auth
from app.utils.response import success, APIError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
def list_conversations(
    keyword: str = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """会话列表"""
    items, total = conversation_service.get_list(db, keyword=keyword, page=page, page_size=page_size)
    return success({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{conv_id}")
def get_conversation(conv_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """会话详情（含消息历史）"""
    return success(conversation_service.get_detail(db, conv_id))


@router.post("")
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db), user=Depends(require_auth)):
    """创建会话"""
    conv = conversation_service.create(db, data)
    return success(conversation_service.get_detail(db, conv.id), message="创建成功")


@router.put("/{conv_id}")
def update_conversation(conv_id: int, data: ConversationUpdate, db: Session = Depends(get_db), user=Depends(require_auth)):
    """更新会话"""
    conv = conversation_service.update(db, conv_id, data)
    return success(conversation_service.get_detail(db, conv.id), message="更新成功")


@router.delete("/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """删除会话"""
    conversation_service.delete(db, conv_id)
    return success(message="删除成功")


@router.post("/{conv_id}/ask")
async def ask_in_conversation(
    conv_id: int,
    data: ConversationAsk,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """会话内流式问答

    检索范围：会话关联的知识库（不走 Skill 路由）
    """
    conv = conversation_service.get_by_id(db, conv_id)
    kb_ids = [kb.id for kb in conv.knowledge_bases]
    if not kb_ids:
        raise APIError("会话未关联任何知识库，无法问答", status_code=400)
    # 获取对话历史
    history = conversation_service.get_history(db, conv_id, turns=data.history_turns)
    # 保存用户消息
    conversation_service.add_message(db, conv_id, role="user", content=data.question)

    # 使用一个空的 Skill 对象作为占位（会话模式不走 Skill 路由，但 rag_service 需要 skill 参数）
    dummy_skill = Skill(
        id=0,
        name="会话问答",
        system_prompt="你是一个专业的知识库助手，基于提供的参考资料回答问题。",
        knowledge_scope="[]",
        enable_query_rewrite=False,
        context_turns=data.history_turns,
    )

    async def event_stream():
        """SSE 流式输出"""
        start = time.time()
        full_answer = []
        sources = []
        token_input = 0
        token_output = 0
        model_name = ""
        degraded = False
        low_confidence = False
        try:
            async for chunk in rag_service.answer_stream(
                question=data.question,
                skill=dummy_skill,
                db=db,
                history=history,
                knowledge_base_ids=kb_ids,
            ):
                ctype = chunk.get("type")
                if ctype == "sources":
                    sources = chunk.get("sources", [])
                    degraded = chunk.get("degraded", False)
                    low_confidence = chunk.get("low_confidence", False)
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'degraded': degraded, 'low_confidence': low_confidence}, ensure_ascii=False)}\n\n"
                elif ctype == "chunk":
                    content = chunk.get("content", "")
                    full_answer.append(content)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': content}, ensure_ascii=False)}\n\n"
                elif ctype == "done":
                    sources = chunk.get("sources", sources)
                    token_input = chunk.get("token_input", 0)
                    token_output = chunk.get("token_output", 0)
                    model_name = chunk.get("model", "")
                    yield f"data: {json.dumps({'type': 'done', 'answer': ''.join(full_answer), 'sources': sources, 'token_input': token_input, 'token_output': token_output, 'model': model_name, 'degraded': degraded, 'low_confidence': low_confidence}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"[conversation.ask] 流式问答失败 conv_id={conv_id}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'问答失败: {str(e)[:200]}'}, ensure_ascii=False)}\n\n"
        finally:
            # 保存助手回复
            answer_text = "".join(full_answer)
            if answer_text:
                conversation_service.add_message(
                    db, conv_id, role="assistant", content=answer_text,
                    sources=sources, token_input=token_input, token_output=token_output,
                    duration_ms=int((time.time() - start) * 1000), model_name=model_name,
                )
            # 记录 token 用量
            if token_input or token_output:
                try:
                    from app.models import TokenUsage
                    usage = TokenUsage(
                        call_type="conversation",
                        source="conversation",
                        input_tokens=token_input,
                        output_tokens=token_output,
                        model_name=model_name,
                    )
                    db.add(usage)
                    db.commit()
                except Exception:
                    logger.exception("[conversation.ask] 记录 token 用量失败")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{conv_id}/messages")
def clear_messages(conv_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """清空会话消息历史"""
    from app.models import ConversationMessage
    conv = conversation_service.get_by_id(db, conv_id)
    db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv_id).delete()
    db.commit()
    return success(message="已清空消息历史")
