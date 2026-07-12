"""RAG 检索增强服务（支持向量 + BM25 混合检索 + RRF 融合）"""
import json
import logging
import re
import time
from typing import AsyncGenerator, Optional

from app.services.vector_store import vector_store
from app.services.embedding_service import embedding_service
from app.services.llm_client import model_manager
from app.services.prompt_assembler import assemble as assemble_prompt
from app.utils.response import APIError

logger = logging.getLogger(__name__)

# RRF 融合参数
RRF_K = 60

# 标点符号正则（用于过滤分词结果）
_PUNCT_RE = re.compile(r'^[\s,，。.!！?？;；、:：()（）\[\]【】""\'\"·\-—…]+$')


def _tokenize_keywords(text: str) -> list:
    """对查询文本进行中文分词，返回去重后的关键词列表。

    使用 jieba 分词（若可用），回退到简单正则切分。
    过滤单字符、纯标点、纯空白。
    """
    if not text or not text.strip():
        return []
    try:
        import jieba
        raw_tokens = list(jieba.cut(text))
    except ImportError:
        logger.warning("[tokenize] jieba 未安装，回退到正则切分（中文检索质量会降低）")
        raw_tokens = re.split(r'[\s,，。.!！?？;；、:：]+', text)
    except Exception:
        raw_tokens = re.split(r'[\s,，。.!！?？;；、:：]+', text)

    keywords = []
    seen = set()
    for t in raw_tokens:
        t = t.strip()
        if not t or len(t) < 2:
            continue
        if _PUNCT_RE.match(t):
            continue
        if t not in seen:
            seen.add(t)
            keywords.append(t)
    return keywords


class RAGService:
    """RAG 检索增强生成服务"""

    async def answer(self, question: str, skill, db, q_embedding: list = None) -> dict:
        """完整 RAG 流程

        Args:
            q_embedding: 预计算的查询向量（N8: 避免重复 Embedding 调用）。None 时内部计算。

        Returns:
            dict: {answer, sources, token_input, token_output, duration_ms, degraded}
        """
        start = time.time()
        # 1. 混合检索（向量 + BM25）
        results = []
        sources = []
        q_vec = q_embedding  # N8: 复用调用方已计算的向量
        degraded = False
        if q_vec is None:
            try:
                q_vecs = await embedding_service.embed([question], source="qa")
                if q_vecs:
                    q_vec = q_vecs[0]
            except APIError:
                degraded = True  # 无 Embedding 模型，仅用 BM25，标记降级
            except Exception:
                degraded = True
                logger.exception(f"[rag.answer] Embedding 失败 question={question[:50]}")

        # 混合检索（即使无 Embedding 也可走 BM25）
        results = self._hybrid_search(q_vec, question, skill, db)

        # 组装 sources
        for r in results:
            meta = r.get("metadata", {})
            sources.append({
                "knowledge_id": int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0,
                "title": meta.get("title", "未知来源"),
                "snippet": (r.get("document", "") or "")[:200],
                "score": r.get("score", 0.0),
            })

        # 2. 组装 Prompt
        messages = assemble_prompt(skill, question, results)

        # 3. 调用 LLM 生成答案
        llm = model_manager.get_active_llm()
        result = await llm.chat(messages)

        duration_ms = int((time.time() - start) * 1000)
        return {
            "answer": result.get("content", ""),
            "sources": sources,
            "token_input": result.get("input_tokens", 0),
            "token_output": result.get("output_tokens", 0),
            "duration_ms": duration_ms,
            "model": result.get("model", ""),
            "degraded": degraded,
        }

    async def answer_stream(self, question: str, skill, db, q_embedding: list = None) -> AsyncGenerator[dict, None]:
        """流式 RAG 流程

        Args:
            q_embedding: 预计算的查询向量（N8: 避免重复 Embedding 调用）。None 时内部计算。

        yield: dict with type field
        """
        start = time.time()
        # 1. Embedding + 混合检索
        results = []
        sources = []
        q_vec = q_embedding  # N8: 复用调用方已计算的向量
        degraded = False
        if q_vec is None:
            try:
                q_vecs = await embedding_service.embed([question], source="qa")
                if q_vecs:
                    q_vec = q_vecs[0]
            except APIError:
                degraded = True  # 无 Embedding 模型，仅用 BM25，标记降级
            except Exception:
                degraded = True
                logger.exception(f"[rag.answer_stream] Embedding 失败 question={question[:50]}")

        # 混合检索
        results = self._hybrid_search(q_vec, question, skill, db)

        # 组装 sources
        for r in results:
            meta = r.get("metadata", {})
            sources.append({
                "knowledge_id": int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0,
                "title": meta.get("title", "未知来源"),
                "snippet": (r.get("document", "") or "")[:200],
                "score": r.get("score", 0.0),
            })

        # 先 yield 来源（附带降级标记）
        yield {"type": "sources", "sources": sources, "degraded": degraded}

        # 2. 组装 Prompt
        messages = assemble_prompt(skill, question, results)

        # 3. 流式生成
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
            "degraded": degraded,
        }

    def _parse_scope(self, skill) -> dict:
        """解析 skill.knowledge_scope"""
        try:
            return json.loads(skill.knowledge_scope) if skill.knowledge_scope else {}
        except Exception:
            logger.exception(f"[rag._parse_scope] 解析 knowledge_scope 失败 skill_id={skill.id}")
            return {}

    def get_search_scope(self, skill) -> Optional[dict]:
        """根据 skill.knowledge_scope 构建 ChromaDB where 过滤条件"""
        scope = self._parse_scope(skill)
        category_ids = scope.get("category_ids", [])
        if not category_ids:
            return None
        cat_strs = [str(c) for c in category_ids]
        if len(cat_strs) == 1:
            return {"category_id": cat_strs[0]}
        return {"category_id": {"$in": cat_strs}}

    def _hybrid_search(self, q_vec, question: str, skill, db, top_k: int = 5) -> list:
        """混合检索：向量 + BM25 + RRF 融合

        Args:
            q_vec: 查询向量（None 时仅走 BM25）
            question: 用户问题文本
            skill: Skill 对象
            db: 数据库会话
            top_k: 最终返回的 chunk 数

        Returns:
            list of dict: [{id, document, metadata, score}]
        """
        scope = self._parse_scope(skill)
        tag_ids = scope.get("tag_ids", [])
        where = self.get_search_scope(skill)

        # 召回数：有 tag_ids 过滤时扩大召回
        recall_k = top_k * 3 if tag_ids else top_k * 2

        # 1. 向量检索
        vec_results = []
        if q_vec:
            try:
                vec_results = vector_store.search(
                    query_embedding=q_vec, where=where, top_k=recall_k
                )
            except Exception:
                logger.exception(f"[rag._hybrid_search] 向量检索失败")

        # 2. BM25 关键词检索
        bm25_kids = self._bm25_search(db, question, scope, limit=recall_k)

        # 3. 合并：knowledge_id → best chunk
        kid_to_chunk = {}
        vec_ranked_kids = []

        for r in vec_results:
            meta = r.get("metadata", {})
            kid = int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0
            if not kid:
                continue
            if kid not in kid_to_chunk or r.get("score", 0) > kid_to_chunk[kid].get("score", 0):
                kid_to_chunk[kid] = r
                vec_ranked_kids.append(kid) if kid not in vec_ranked_kids else None

        # 去重 vec_ranked_kids 并按 score 排序
        vec_ranked_kids = sorted(
            set(kid_to_chunk.keys()),
            key=lambda k: kid_to_chunk[k].get("score", 0),
            reverse=True
        )

        # 4. 为 BM25 命中但向量未命中的 knowledge 补充 chunk
        for kid in bm25_kids:
            if kid not in kid_to_chunk:
                chunks = vector_store.get_by_knowledge_id(kid, limit=1)
                if chunks:
                    kid_to_chunk[kid] = chunks[0]

        # 5. tag_ids 应用层过滤
        if tag_ids:
            try:
                from app.models.knowledge import knowledge_tags
                from sqlalchemy import select

                stmt = select(knowledge_tags.c.knowledge_id).where(
                    knowledge_tags.c.tag_id.in_(tag_ids)
                )
                allowed_kids = set(db.execute(stmt).scalars().all())

                vec_ranked_kids = [k for k in vec_ranked_kids if k in allowed_kids]
                bm25_kids = [k for k in bm25_kids if k in allowed_kids]
            except Exception:
                logger.exception(f"[rag._hybrid_search] tag_ids 过滤失败")

        # 6. RRF 融合
        fused = self._rrf_fuse(vec_ranked_kids, bm25_kids)

        # 7. 取 top_k 个 knowledge_id，返回对应 chunk
        result = []
        for kid, _ in fused[:top_k]:
            if kid in kid_to_chunk:
                result.append(kid_to_chunk[kid])

        return result

    def _bm25_search(self, db, question: str, scope: dict, limit: int = 10) -> list:
        """BM25 关键词检索（基于 SQLite LIKE + 简单评分）

        Args:
            db: 数据库会话
            question: 用户问题
            scope: {"category_ids": [], "tag_ids": []}
            limit: 最多返回的 knowledge_id 数

        Returns:
            list of int: 按相关性排序的 knowledge_id 列表
        """
        from app.models import Knowledge
        from app.models.knowledge import knowledge_tags
        from sqlalchemy import or_

        # 提取关键词（jieba 中文分词 + 标点过滤）
        keywords = _tokenize_keywords(question)
        if not keywords:
            return []

        q = db.query(Knowledge)

        # Scope 过滤
        category_ids = scope.get("category_ids", [])
        tag_ids = scope.get("tag_ids", [])
        if category_ids:
            q = q.filter(Knowledge.category_id.in_(category_ids))
        if tag_ids:
            q = q.join(knowledge_tags).filter(knowledge_tags.c.tag_id.in_(tag_ids)).distinct()

        # 关键词匹配
        conditions = []
        for kw in keywords:
            conditions.append(Knowledge.title.like(f"%{kw}%"))
            conditions.append(Knowledge.content.like(f"%{kw}%"))

        if not conditions:
            return []

        q = q.filter(or_(*conditions))
        items = q.all()

        # 简单评分：标题命中 = 2 分，内容命中 = 1 分
        ranked = []
        for k in items:
            score = 0
            for kw in keywords:
                if kw in (k.title or ""):
                    score += 2
                if kw in (k.content or ""):
                    score += 1
            if score > 0:
                ranked.append((k.id, score))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return [kid for kid, _ in ranked[:limit]]

    def _rrf_fuse(self, vec_ranked: list, bm25_ranked: list, k: int = RRF_K) -> list:
        """RRF (Reciprocal Rank Fusion) 融合两路检索结果

        公式: score(d) = Σ 1/(k + rank_i(d))

        Args:
            vec_ranked: 向量检索的 knowledge_id 排序列表
            bm25_ranked: BM25 检索的 knowledge_id 排序列表
            k: RRF 参数（默认 60）

        Returns:
            list of (knowledge_id, rrf_score) 按分数降序
        """
        scores = {}

        for rank, kid in enumerate(vec_ranked):
            scores[kid] = scores.get(kid, 0) + 1.0 / (k + rank + 1)

        for rank, kid in enumerate(bm25_ranked):
            scores[kid] = scores.get(kid, 0) + 1.0 / (k + rank + 1)

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)


rag_service = RAGService()
