"""问答服务"""
import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from app.models import QAHistory, TokenUsage
from app.services.skill_router import route as skill_route, test_route
from app.services.rag_service import rag_service
from app.services.cache_service import answer_cache
from app.services.embedding_service import embedding_service
from app.services.knowledge_service import _run_async
from app.utils.response import APIError

logger = logging.getLogger(__name__)


async def ask(db, question: str, use_cache: bool = True):
    """完整问答流程"""
    start = time.time()
    # 1. Skill 路由
    skill, match_type, score = skill_route(question, db)

    # 2. 检查缓存
    cached = None
    q_embedding = None
    if use_cache:
        try:
            vecs = await embedding_service.embed([question], source="qa_cache")
            if vecs:
                q_embedding = vecs[0]
                cached = answer_cache.get(q_embedding)
        except APIError:
            # 没有配置 Embedding 模型，跳过缓存
            pass
        except Exception:
            pass

    if cached:
        cached["cached"] = True
        # 保存历史
        history = QAHistory(
            question=question,
            answer=cached.get("answer", ""),
            sources=json.dumps(cached.get("sources", []), ensure_ascii=False),
            skill_id=skill.id,
            skill_name=skill.name,
            token_input=0,
            token_output=0,
            duration_ms=int((time.time() - start) * 1000),
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        cached["history_id"] = history.id
        cached["skill_id"] = skill.id
        cached["skill_name"] = skill.name
        return cached

    # 3. RAG 检索 + 生成
    result = await rag_service.answer(question, skill, db)
    duration_ms = int((time.time() - start) * 1000)

    # 4. 保存 QAHistory
    history = QAHistory(
        question=question,
        answer=result["answer"],
        sources=json.dumps(result["sources"], ensure_ascii=False),
        skill_id=skill.id,
        skill_name=skill.name,
        token_input=result["token_input"],
        token_output=result["token_output"],
        duration_ms=duration_ms,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    # 5. 记录 TokenUsage（使用实际模型名）
    usage = TokenUsage(
        call_type="chat",
        model_name=result.get("model") or "llm",
        input_tokens=result["token_input"],
        output_tokens=result["token_output"],
        duration_ms=duration_ms,
        skill_id=skill.id,
        qa_history_id=history.id,
        source="qa",
    )
    db.add(usage)
    db.commit()

    # 写入缓存
    if use_cache and q_embedding:
        try:
            answer_cache.put(
                question=question,
                answer={
                    "answer": result["answer"],
                    "sources": result["sources"],
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                },
                question_embedding=q_embedding,
            )
        except Exception:
            pass

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "skill_id": skill.id,
        "skill_name": skill.name,
        "token_input": result["token_input"],
        "token_output": result["token_output"],
        "duration_ms": duration_ms,
        "cached": False,
        "history_id": history.id,
    }


async def ask_stream(db, question: str, use_cache: bool = True) -> AsyncGenerator[str, None]:
    """SSE 流式问答

    yield: f"data: {json.dumps(chunk)}\n\n"
    """
    # 1. Skill 路由
    skill, match_type, score = skill_route(question, db)
    yield _sse({"type": "skill", "skill_id": skill.id, "skill_name": skill.name,
                "match_type": match_type, "score": score})

    # 2. RAG 流式
    full_answer = []
    sources = []
    token_input = 0
    token_output = 0
    duration_ms = 0
    model_name = ""
    start = time.time()
    cancelled = False
    try:
        async for chunk in rag_service.answer_stream(question, skill, db):
            if chunk["type"] == "sources":
                sources = chunk["sources"]
                yield _sse({"type": "sources", "sources": sources})
            elif chunk["type"] == "chunk":
                full_answer.append(chunk["content"])
                yield _sse({"type": "chunk", "content": chunk["content"]})
            elif chunk["type"] == "done":
                sources = chunk.get("sources", sources)
                token_input = chunk.get("token_input", 0)
                token_output = chunk.get("token_output", 0)
                duration_ms = chunk.get("duration_ms", 0)
                model_name = chunk.get("model", "")
    except asyncio.CancelledError:
        # 客户端取消（关闭页面/点击停止），保存已生成的部分答案
        cancelled = True
        logger.info(f"问答流被取消，保存部分答案: question={question[:50]}, 已生成{len(full_answer)}片段")
        duration_ms = int((time.time() - start) * 1000)
        # 不重新抛出，继续执行保存逻辑（使用已生成的部分答案）

    duration_ms = duration_ms or int((time.time() - start) * 1000)

    answer_text = "".join(full_answer)
    if not answer_text:
        answer_text = "（生成被中断，未获取到完整答案）"

    # 3. 保存历史
    history = QAHistory(
        question=question,
        answer=answer_text,
        sources=json.dumps(sources, ensure_ascii=False),
        skill_id=skill.id,
        skill_name=skill.name,
        token_input=token_input,
        token_output=token_output,
        duration_ms=duration_ms,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    # 4. 记录 TokenUsage（使用实际模型名）
    usage = TokenUsage(
        call_type="chat",
        model_name=model_name or "llm",
        input_tokens=token_input,
        output_tokens=token_output,
        duration_ms=duration_ms,
        skill_id=skill.id,
        qa_history_id=history.id,
        source="qa",
    )
    db.add(usage)
    db.commit()

    # 5. 结束事件
    yield _sse({
        "type": "done",
        "answer": answer_text,
        "sources": sources,
        "skill_id": skill.id,
        "skill_name": skill.name,
        "token_input": token_input,
        "token_output": token_output,
        "duration_ms": duration_ms,
        "history_id": history.id,
        "cancelled": cancelled,
    })


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def feedback(db, history_id: int, feedback_value: int) -> bool:
    """记录反馈"""
    h = db.query(QAHistory).filter(QAHistory.id == history_id).first()
    if not h:
        raise APIError("问答记录不存在", status_code=404)
    h.feedback = feedback_value
    db.commit()
    return True


def get_suggestions(db, question: str, answer: str = "") -> list:
    """推荐追问问题（基于关键词简单实现）"""
    suggestions = []
    # 根据问题中关键词生成
    if "故障" in question or "报错" in question:
        suggestions.append("这个故障的根本原因是什么？")
        suggestions.append("如何预防这类故障？")
        suggestions.append("还有哪些相关的故障代码？")
    elif "保养" in question or "维护" in question:
        suggestions.append("保养周期应该怎么安排？")
        suggestions.append("保养时需要注意什么？")
        suggestions.append("保养记录如何管理？")
    elif "工艺" in question or "参数" in question:
        suggestions.append("这些参数的允许范围是多少？")
        suggestions.append("参数调整对质量有什么影响？")
        suggestions.append("相关工序有哪些？")
    elif "质量" in question or "检验" in question:
        suggestions.append("质量标准的具体数值是多少？")
        suggestions.append("不合格品如何处理？")
        suggestions.append("检验方法有哪些？")
    else:
        suggestions.append("能否提供更多细节？")
        suggestions.append("相关文档有哪些？")
        suggestions.append("还有什么需要注意的事项？")
    return suggestions[:3]


def get_history(db, page: int = 1, page_size: int = 10, keyword: str = None):
    """问答历史列表"""
    q = db.query(QAHistory)
    if keyword:
        q = q.filter(QAHistory.question.like(f"%{keyword}%") | QAHistory.answer.like(f"%{keyword}%"))
    total = q.count()
    items = q.order_by(QAHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    out = []
    for h in items:
        out.append({
            "id": h.id,
            "question": h.question,
            "answer_summary": (h.answer or "")[:100],
            "skill_name": h.skill_name,
            "created_at": h.created_at,
        })
    return out, total


def delete_history(db, id: int):
    """删除历史"""
    h = db.query(QAHistory).filter(QAHistory.id == id).first()
    if not h:
        raise APIError("问答记录不存在", status_code=404)
    db.delete(h)
    db.commit()


def get_history_detail(db, id: int):
    """历史详情"""
    h = db.query(QAHistory).filter(QAHistory.id == id).first()
    if not h:
        raise APIError("问答记录不存在", status_code=404)
    try:
        sources = json.loads(h.sources) if h.sources else []
    except Exception:
        sources = []
    return {
        "id": h.id,
        "question": h.question,
        "answer": h.answer,
        "sources": sources,
        "skill_id": h.skill_id,
        "skill_name": h.skill_name,
        "feedback": h.feedback,
        "token_input": h.token_input,
        "token_output": h.token_output,
        "duration_ms": h.duration_ms,
        "created_at": h.created_at,
    }
