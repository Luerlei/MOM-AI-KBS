"""RAG 检索增强服务"""
import json
import time
from typing import AsyncGenerator

from app.services.vector_store import vector_store
from app.services.embedding_service import embedding_service
from app.services.llm_client import model_manager
from app.services.prompt_assembler import assemble as assemble_prompt
from app.services.knowledge_service import _run_async
from app.utils.response import APIError


class RAGService:
    """RAG 检索增强生成服务"""

    async def answer(self, question: str, skill, db) -> dict:
        """完整 RAG 流程

        Returns:
            dict: {answer, sources, token_input, token_output, duration_ms}
        """
        start = time.time()
        # 1. 尝试 Embedding 问题（无 Embedding 模型时降级为直接对话）
        results = []
        sources = []
        try:
            q_vecs = await embedding_service.embed([question], source="qa")
            if q_vecs:
                q_vec = q_vecs[0]
                # 2. 在 Skill 知识范围内检索
                where = self.get_search_scope(skill)
                results = vector_store.search(query_embedding=q_vec, where=where, top_k=5)
                for r in results:
                    meta = r.get("metadata", {})
                    sources.append({
                        "knowledge_id": int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0,
                        "title": meta.get("title", "未知来源"),
                        "snippet": (r.get("document", "") or "")[:200],
                        "score": r.get("score", 0.0),
                    })
        except APIError:
            pass
        except Exception:
            pass

        # 4. 组装 Prompt
        messages = assemble_prompt(skill, question, results)

        # 5. 调用 LLM 生成答案
        llm = model_manager.get_active_llm()
        result = await llm.chat(messages)

        duration_ms = int((time.time() - start) * 1000)
        return {
            "answer": result.get("content", ""),
            "sources": sources,
            "token_input": result.get("input_tokens", 0),
            "token_output": result.get("output_tokens", 0),
            "duration_ms": duration_ms,
        }

    async def answer_stream(self, question: str, skill, db) -> AsyncGenerator[dict, None]:
        """流式 RAG 输出

        yield:
            {"type": "sources", "sources": [...]}  先来源
            {"type": "chunk", "content": "..."}   答案片段
            {"type": "done", "sources": [...], "token_input":..., "token_output":..., "duration_ms":...}
        """
        start = time.time()
        # 1. 尝试 Embedding 问题（无 Embedding 模型时降级为直接对话）
        results = []
        sources = []
        try:
            q_vecs = await embedding_service.embed([question], source="qa")
            if q_vecs:
                q_vec = q_vecs[0]
                # 2. 检索
                where = self.get_search_scope(skill)
                results = vector_store.search(query_embedding=q_vec, where=where, top_k=5)
                for r in results:
                    meta = r.get("metadata", {})
                    sources.append({
                        "knowledge_id": int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0,
                        "title": meta.get("title", "未知来源"),
                        "snippet": (r.get("document", "") or "")[:200],
                        "score": r.get("score", 0.0),
                    })
        except APIError:
            # 无 Embedding 模型，跳过检索
            pass
        except Exception:
            pass

        # 先 yield 来源
        yield {"type": "sources", "sources": sources}

        # 3. 组装 Prompt
        messages = assemble_prompt(skill, question, results)

        # 4. 流式生成
        llm = model_manager.get_active_llm()
        full_answer = []
        async for piece in llm.chat_stream(messages):
            full_answer.append(piece)
            yield {"type": "chunk", "content": piece}

        # 从 LLM 客户端读取最后一次流式调用的 usage 信息
        usage = getattr(llm, "last_usage", {}) or {}
        duration_ms = int((time.time() - start) * 1000)
        yield {
            "type": "done",
            "answer": "".join(full_answer),
            "sources": sources,
            "token_input": usage.get("input_tokens", 0),
            "token_output": usage.get("output_tokens", 0),
            "model": usage.get("model", ""),
            "duration_ms": duration_ms,
        }

    def get_search_scope(self, skill) -> dict:
        """根据 skill.knowledge_scope 构建 ChromaDB where 过滤条件

        scope 形如 {"category_ids":[1,2], "tag_ids":[3]}
        ChromaDB where 仅支持单字段过滤，这里只按 category_id 过滤（若有）。
        tag_ids 过滤需要在应用层做。
        """
        try:
            scope = json.loads(skill.knowledge_scope) if skill.knowledge_scope else {}
        except Exception:
            scope = {}

        category_ids = scope.get("category_ids", [])
        if not category_ids:
            return None
        # ChromaDB where: category_id in [...]
        cat_strs = [str(c) for c in category_ids]
        if len(cat_strs) == 1:
            return {"category_id": cat_strs[0]}
        # 多个值用 $in
        return {"category_id": {"$in": cat_strs}}


rag_service = RAGService()
