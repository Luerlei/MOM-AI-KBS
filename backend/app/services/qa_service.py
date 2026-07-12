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
from app.utils.response import APIError

logger = logging.getLogger(__name__)


async def ask(db, question: str, use_cache: bool = True, history: list = None):
    """完整问答流程"""
    start = time.time()
    # 1. Skill 路由
    skill, match_type, score = await skill_route(question, db)

    # 2. 检查缓存
    cached = None
    q_embedding = None
    if use_cache and not history:
        # 有对话历史时不查缓存（改写后的查询与原缓存不匹配）
        try:
            vecs = await embedding_service.embed([question], source="qa_cache")
            if vecs:
                q_embedding = vecs[0]
                cached = answer_cache.get(q_embedding)
        except APIError:
            # 没有配置 Embedding 模型，跳过缓存
            pass
        except Exception:
            logger.exception(f"[ask] 检查缓存失败 question={question[:50]}")

    if cached:
        cached["cached"] = True
        # 保存历史（N10: 标记 is_cache_hit=1）
        history = QAHistory(
            question=question,
            answer=cached.get("answer", ""),
            sources=json.dumps(cached.get("sources", []), ensure_ascii=False),
            skill_id=skill.id,
            skill_name=skill.name,
            token_input=0,
            token_output=0,
            duration_ms=int((time.time() - start) * 1000),
            is_cache_hit=1,
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        cached["history_id"] = history.id
        cached["skill_id"] = skill.id
        cached["skill_name"] = skill.name
        return cached

    # 3. RAG 检索 + 生成（N8: 复用已计算的 q_embedding 避免重复 Embedding）
    result = await rag_service.answer(question, skill, db, q_embedding=q_embedding, history=history)
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
            logger.exception(f"[ask] 写入缓存失败 question={question[:50]}")

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
        "degraded": result.get("degraded", False),
    }


async def ask_stream(db, question: str, use_cache: bool = True, history: list = None) -> AsyncGenerator[str, None]:
    """SSE 流式问答

    yield: f"data: {json.dumps(chunk)}\n\n"
    """
    # 1. Skill 路由
    skill, match_type, score = await skill_route(question, db)
    yield _sse({"type": "skill", "skill_id": skill.id, "skill_name": skill.name,
                "match_type": match_type, "score": score})

    # 1b. 检查缓存（命中则一次性推送完整答案，跳过 RAG 流式）
    # 有对话历史时不查缓存（改写后的查询与原缓存不匹配）
    q_embedding = None  # N8: 保存查询向量供 RAG 和写缓存复用
    if use_cache and not history:
        cached = None
        cache_start = time.time()
        try:
            vecs = await embedding_service.embed([question], source="qa_cache")
            if vecs:
                q_embedding = vecs[0]  # N8: 保存向量供后续复用
                cached = answer_cache.get(q_embedding)
        except APIError:
            pass  # 无 Embedding 模型，跳过缓存
        except Exception:
            logger.exception(f"[ask_stream] 检查缓存失败 question={question[:50]}")

        if cached:
            cache_duration_ms = int((time.time() - cache_start) * 1000)
            cached["cached"] = True
            cached["history_id"] = None  # 流式缓存命中不保存历史（历史已在 ask() 中保存）
            cached["degraded"] = False
            # 保存 QAHistory（记录实际 Embedding + 缓存查询耗时；N10: 标记 is_cache_hit=1）
            try:
                history = QAHistory(
                    question=question,
                    answer=cached.get("answer", ""),
                    sources=json.dumps(cached.get("sources", []), ensure_ascii=False),
                    skill_id=skill.id,
                    skill_name=skill.name,
                    token_input=0,
                    token_output=0,
                    duration_ms=cache_duration_ms,
                    is_cache_hit=1,
                )
                db.add(history)
                db.commit()
                db.refresh(history)
                cached["history_id"] = history.id
            except Exception:
                logger.exception(f"[ask_stream] 缓存命中保存历史失败")

            yield _sse({
                "type": "sources",
                "sources": cached.get("sources", []),
                "degraded": False,
            })
            yield _sse({"type": "chunk", "content": cached.get("answer", "")})
            yield _sse({
                "type": "done",
                "answer": cached.get("answer", ""),
                "sources": cached.get("sources", []),
                "skill_id": skill.id,
                "skill_name": skill.name,
                "token_input": 0,
                "token_output": 0,
                "duration_ms": cache_duration_ms,
                "history_id": cached.get("history_id"),
                "cancelled": False,
                "degraded": False,
            })
            return

    # 2. RAG 流式
    full_answer = []
    sources = []
    token_input = 0
    token_output = 0
    duration_ms = 0
    model_name = ""
    degraded = False
    start = time.time()
    cancelled = False
    try:
        async for chunk in rag_service.answer_stream(question, skill, db, q_embedding=q_embedding, history=history):
            if chunk["type"] == "sources":
                sources = chunk["sources"]
                degraded = chunk.get("degraded", False)
                yield _sse({"type": "sources", "sources": sources, "degraded": degraded})
            elif chunk["type"] == "chunk":
                full_answer.append(chunk["content"])
                yield _sse({"type": "chunk", "content": chunk["content"]})
            elif chunk["type"] == "done":
                sources = chunk.get("sources", sources)
                token_input = chunk.get("token_input", 0)
                token_output = chunk.get("token_output", 0)
                duration_ms = chunk.get("duration_ms", 0)
                model_name = chunk.get("model", "")
                degraded = chunk.get("degraded", degraded)
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

    # 4b. 写入缓存（流式问答完成后缓存答案，供下次命中）
    # N8: 复用 q_embedding 避免第三次 Embedding 调用；无缓存向量时才重新计算
    if use_cache:
        cache_vec = q_embedding
        if cache_vec is None:
            try:
                vecs = await embedding_service.embed([question], source="qa_cache")
                if vecs:
                    cache_vec = vecs[0]
            except APIError:
                pass  # 无 Embedding 模型，跳过缓存
            except Exception:
                logger.exception(f"[ask_stream] 写缓存 Embedding 失败 question={question[:50]}")
        if cache_vec:
            try:
                answer_cache.put(
                    question=question,
                    answer={
                        "answer": answer_text,
                        "sources": sources,
                        "skill_id": skill.id,
                        "skill_name": skill.name,
                    },
                    question_embedding=cache_vec,
                )
            except Exception:
                logger.exception(f"[ask_stream] 写入缓存失败 question={question[:50]}")

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
        "degraded": degraded,
    })


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def feedback(db, history_id: int, feedback_value) -> bool:
    """记录反馈

    Args:
        feedback_value: 接受 "useful"/"useless" 字符串或 1/-1 整数
    """
    h = db.query(QAHistory).filter(QAHistory.id == history_id).first()
    if not h:
        raise APIError("问答记录不存在", status_code=404)
    # 统一转为 int：useful=1, useless=-1
    if isinstance(feedback_value, str):
        fb_map = {"useful": 1, "useless": -1}
        fb_int = fb_map.get(feedback_value.lower().strip(), 0)
    else:
        fb_int = int(feedback_value)
    if fb_int not in (1, -1):
        raise APIError("反馈值无效，应为 useful/useless 或 1/-1", status_code=400)
    h.feedback = fb_int
    db.commit()
    return True


async def get_suggestions(db, question: str, answer: str = "") -> list:
    """推荐追问问题

    优先使用 LLM 基于当前 Q&A 上下文生成，失败时回退到关键词匹配。
    """
    # 尝试 LLM 生成追问
    try:
        from app.services.llm_client import model_manager
        llm = model_manager.get_active_llm()
        prompt = f"""基于以下用户问题和AI回答，生成3个相关的追问问题。
要求：
1. 问题简短（不超过20字）
2. 与当前话题相关但角度不同
3. 帮助用户深入探索主题

用户问题：{question}
AI回答：{(answer or "")[:500]}

请直接输出3个问题，每行一个，不要编号和额外说明。"""

        result = await llm.chat([
            {"role": "system", "content": "你是一个智能问答助手，擅长生成相关的追问问题。"},
            {"role": "user", "content": prompt},
        ])
        content = result.get("content", "").strip()
        if content:
            lines = [l.strip().lstrip("0123456789.、-）) ").strip() for l in content.split("\n") if l.strip()]
            suggestions = [l for l in lines if l][:3]
            if suggestions:
                return suggestions
    except Exception:
        logger.debug("[get_suggestions] LLM 生成追问失败，回退到关键词匹配")

    # 回退：基于关键词匹配
    if "故障" in question or "报错" in question:
        return ["这个故障的根本原因是什么？", "如何预防这类故障？", "还有哪些相关的故障代码？"]
    elif "保养" in question or "维护" in question:
        return ["保养周期应该怎么安排？", "保养时需要注意什么？", "保养记录如何管理？"]
    elif "工艺" in question or "参数" in question:
        return ["这些参数的允许范围是多少？", "参数调整对质量有什么影响？", "相关工序有哪些？"]
    elif "质量" in question or "检验" in question:
        return ["质量标准的具体数值是多少？", "不合格品如何处理？", "检验方法有哪些？"]
    else:
        return ["能否提供更多细节？", "相关文档有哪些？", "还有什么需要注意的事项？"]


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
            "answer": (h.answer or "")[:200],
            "answer_summary": (h.answer or "")[:100],
            "skill_name": h.skill_name,
            "total_tokens": (h.token_input or 0) + (h.token_output or 0),
            "input_tokens": h.token_input,
            "output_tokens": h.token_output,
            "feedback": h.feedback,
            "is_cache_hit": h.is_cache_hit or 0,  # N10: 显式标记缓存命中
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
