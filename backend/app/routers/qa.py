"""问答路由"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import limiter
from app.schemas.qa import QARequest, QAFeedback
from app.services import qa_service
from app.utils.response import success, page_result
from app.utils.auth import require_auth
from app.config import RATE_LIMIT_QA, RATE_LIMIT_SUGGESTIONS

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/ask")
@limiter.limit(RATE_LIMIT_QA)
async def ask(request: Request, data: QARequest, db: Session = Depends(get_db)):
    """智能问答（SSE 流式返回）"""
    import json
    from app.services.llm_client import ModelManager
    from app.utils.response import error, APIError
    from fastapi.responses import JSONResponse

    # 预检查：至少需要 LLM 模型（Embedding 缺失时 RAG 自动降级为直接对话）
    try:
        ModelManager.get_active_llm()
    except APIError as e:
        return JSONResponse(
            status_code=400,
            content=error(e.message, e.code),
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=error(f"模型配置错误: {str(e)}"),
        )

    async def event_stream():
        import json
        try:
            # 将 history 从 Pydantic 模型转为 dict 列表
            history = [h.dict() for h in data.history] if data.history else None
            async for chunk in qa_service.ask_stream(db, data.question, use_cache=data.use_cache, history=history):
                yield chunk
        except asyncio.CancelledError:
            # 客户端断开连接（关闭页面/点击停止），及时释放资源
            logger.info(f"问答流被客户端取消: question={data.question[:50]}")
            # 不需要 yield 错误，客户端已断开
            raise
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback")
def feedback(data: QAFeedback, db: Session = Depends(get_db)):
    """答案反馈"""
    qa_service.feedback(db, data.history_id, data.feedback)
    return success(message="反馈成功")


@router.get("/suggestions")
@limiter.limit(RATE_LIMIT_SUGGESTIONS)
async def suggestions(request: Request, question: str, answer: Optional[str] = None, db: Session = Depends(get_db)):
    """快捷追问推荐

    Args:
        question: 用户问题
        answer: AI 回答（可选，传入后 LLM 追问质量更高）
    """
    items = await qa_service.get_suggestions(db, question, answer)
    return success(items)


@router.get("/history")
def history(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """问答历史（分页）"""
    items, total = qa_service.get_history(db, page=page, page_size=page_size, keyword=keyword)
    return page_result(items, total, page, page_size)


@router.get("/history/{hid}")
def history_detail(hid: int, db: Session = Depends(get_db)):
    """历史详情"""
    detail = qa_service.get_history_detail(db, hid)
    return success(detail)


@router.delete("/history/{hid}")
def delete_history(hid: int, db: Session = Depends(get_db)):
    """删除历史"""
    qa_service.delete_history(db, hid)
    return success(message="删除成功")
