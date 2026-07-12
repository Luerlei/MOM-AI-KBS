"""RAG 检索增强服务（支持向量 + BM25 混合检索 + RRF 融合）"""
import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from typing import AsyncGenerator, Optional

from app.services.vector_store import vector_store
from app.services.embedding_service import embedding_service
from app.services.llm_client import model_manager
from app.services.prompt_assembler import assemble as assemble_prompt
from app.utils.response import APIError
from app.config import QUERY_REWRITE_CACHE_TTL, QUERY_REWRITE_CACHE_MAXSIZE

logger = logging.getLogger(__name__)


class _RewriteCache:
    """查询改写结果缓存（TTL + LRU 淘汰）

    key = sha1(question + history_hash)
    value = (rewritten_query, created_timestamp)
    """

    def __init__(self, ttl: int, maxsize: int):
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: OrderedDict = OrderedDict()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(question: str, history: list) -> str:
        history_json = json.dumps(history or [], ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(f"{question}|{history_json}".encode("utf-8")).hexdigest()

    def get(self, question: str, history: list) -> Optional[str]:
        key = self._make_key(question, history)
        item = self._store.get(key)
        if item is None:
            self._misses += 1
            return None
        rewritten, ts = item
        if time.time() - ts > self._ttl:
            # 过期
            self._store.pop(key, None)
            self._misses += 1
            return None
        # 命中：移到末尾（LRU）
        self._store.move_to_end(key)
        self._hits += 1
        return rewritten

    def set(self, question: str, history: list, rewritten: str):
        key = self._make_key(question, history)
        self._store[key] = (rewritten, time.time())
        self._store.move_to_end(key)
        # 超出容量时淘汰最老的
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            "size": len(self._store),
            "maxsize": self._maxsize,
            "ttl": self._ttl,
        }


# 全局查询改写缓存实例
rewrite_cache = _RewriteCache(ttl=QUERY_REWRITE_CACHE_TTL, maxsize=QUERY_REWRITE_CACHE_MAXSIZE)

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

    async def answer(self, question: str, skill, db, q_embedding: list = None, history: list = None) -> dict:
        """完整 RAG 流程

        Args:
            q_embedding: 预计算的查询向量（N8: 避免重复 Embedding 调用）。None 时内部计算。
            history: 对话历史 [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]

        Returns:
            dict: {answer, sources, token_input, token_output, duration_ms, degraded}
        """
        start = time.time()
        # 0. 查询改写（可选）
        search_query = question
        rewrite_info = {}
        if history and self._should_rewrite(skill):
            try:
                search_query, rewrite_info = await self._rewrite_query(question, history, skill)
            except Exception:
                logger.warning(f"[rag.answer] 查询改写失败，使用原始问题 skill_id={getattr(skill, 'id', '?')} question='{question[:80]}'", exc_info=True)
                search_query = question

        # 1. 混合检索（向量 + BM25）
        results = []
        sources = []
        q_vec = q_embedding  # N8: 复用调用方已计算的向量
        degraded = False
        if q_vec is None:
            try:
                q_vecs = await embedding_service.embed([search_query], source="qa")
                if q_vecs:
                    q_vec = q_vecs[0]
            except APIError:
                degraded = True  # 无 Embedding 模型，仅用 BM25，标记降级
            except Exception:
                degraded = True
                logger.exception(f"[rag.answer] Embedding 失败 question={search_query[:50]}")

        # 混合检索（即使无 Embedding 也可走 BM25）
        results = self._hybrid_search(q_vec, search_query, skill, db)

        # 相似度阈值过滤：丢弃低于阈值的低质量结果
        results, low_confidence = self._filter_by_relevance(results, degraded)

        # Rerank 重排序（可选，配置了 Rerank 模型时启用）
        results = await self._rerank_results(search_query, results)

        # 组装 sources
        for r in results:
            meta = r.get("metadata", {})
            sources.append({
                "knowledge_id": int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0,
                "title": meta.get("title", "未知来源"),
                "snippet": (r.get("document", "") or "")[:200],
                "score": r.get("score", 0.0),
            })

        # 2. 组装 Prompt（K-1: 传入 history 支持多轮对话）
        messages = assemble_prompt(skill, question, results, history=history)

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
            "low_confidence": low_confidence,
        }

    async def answer_stream(self, question: str, skill, db, q_embedding: list = None, history: list = None) -> AsyncGenerator[dict, None]:
        """流式 RAG 流程

        Args:
            q_embedding: 预计算的查询向量（N8: 避免重复 Embedding 调用）。None 时内部计算。
            history: 对话历史 [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]

        yield: dict with type field
        """
        start = time.time()
        # 0. 查询改写（可选）
        search_query = question
        if history and self._should_rewrite(skill):
            try:
                search_query, _ = await self._rewrite_query(question, history, skill)
            except Exception:
                logger.warning(f"[rag.answer_stream] 查询改写失败，使用原始问题 skill_id={getattr(skill, 'id', '?')} question='{question[:80]}'", exc_info=True)
                search_query = question

        # 1. Embedding + 混合检索
        results = []
        sources = []
        q_vec = q_embedding  # N8: 复用调用方已计算的向量
        degraded = False
        if q_vec is None:
            try:
                q_vecs = await embedding_service.embed([search_query], source="qa")
                if q_vecs:
                    q_vec = q_vecs[0]
            except APIError:
                degraded = True  # 无 Embedding 模型，仅用 BM25，标记降级
            except Exception:
                degraded = True
                logger.exception(f"[rag.answer_stream] Embedding 失败 question={search_query[:50]}")

        # 混合检索
        results = self._hybrid_search(q_vec, search_query, skill, db)

        # 相似度阈值过滤：丢弃低于阈值的低质量结果
        results, low_confidence = self._filter_by_relevance(results, degraded)

        # Rerank 重排序（可选，配置了 Rerank 模型时启用）
        results = await self._rerank_results(search_query, results)

        # 组装 sources
        for r in results:
            meta = r.get("metadata", {})
            sources.append({
                "knowledge_id": int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0,
                "title": meta.get("title", "未知来源"),
                "snippet": (r.get("document", "") or "")[:200],
                "score": r.get("score", 0.0),
            })

        # 先 yield 来源（附带降级标记和低置信度标记）
        yield {"type": "sources", "sources": sources, "degraded": degraded, "low_confidence": low_confidence}

        # 2. 组装 Prompt（K-1: 传入 history 支持多轮对话）
        messages = assemble_prompt(skill, question, results, history=history)

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
            "low_confidence": low_confidence,
        }

    async def _rerank_results(self, query: str, results: list) -> list:
        """Rerank 重排序：配置了 Rerank 模型时对检索结果精排

        策略：
        - 未配置 Rerank 模型 → 直接返回原结果
        - 已配置 → 调用 Rerank API 重新打分排序
        - Rerank 失败 → 回退到原结果（不阻断流程）
        """
        if not results or len(results) <= 1:
            return results

        try:
            reranker = model_manager.get_active_rerank()
        except Exception:
            return results

        if not reranker:
            return results  # 未配置 Rerank 模型，跳过

        # 准备文档文本
        documents = [r.get("document", "") or "" for r in results]
        try:
            ranked = await reranker.rerank(query, documents, top_n=len(results))
            # 按 rerank 分数重新排序 results
            reranked_results = []
            for item in ranked:
                idx = item.get("index", 0)
                if 0 <= idx < len(results):
                    r = results[idx].copy()
                    r["score"] = item.get("relevance_score", r.get("score", 0.0))
                    reranked_results.append(r)
            logger.info(f"[rerank] 重排序完成: {len(reranked_results)} 条结果")
            return reranked_results if reranked_results else results
        except Exception:
            logger.exception("[rerank] 重排序失败，回退到原结果")
            return results

    def _should_rewrite(self, skill) -> bool:
        """判断是否启用查询改写"""
        return getattr(skill, "enable_query_rewrite", False) is True

    async def _rewrite_query(self, question: str, history: list, skill) -> tuple:
        """用 LLM 改写查询，结合对话历史消解指代

        Returns:
            tuple: (改写后的查询, {original, rewritten, tokens, cache_hit})
        """
        from app.services.llm_client import model_manager as _mm

        # 缓存命中检查：相同 question+history 直接返回缓存的改写结果
        cached = rewrite_cache.get(question, history or [])
        if cached is not None:
            logger.info(f"[rewrite] 缓存命中 skill_id={getattr(skill, 'id', '?')} '{question[:50]}' → '{cached[:50]}'")
            return cached, {
                "original": question,
                "rewritten": cached,
                "tokens": 0,
                "cache_hit": True,
            }

        # 构建历史摘要（最近几轮）
        context_turns = getattr(skill, "context_turns", 3) or 3
        recent = history[-(context_turns * 2):] if history else []
        history_text = ""
        for msg in recent:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = (msg.get("content") or "")[:200]
            history_text += f"{role}: {content}\n"

        prompt = f"""请根据对话历史，将用户最新问题改写为一个独立、完整、可检索的查询。
要求：
1. 消解指代词（它、这个、那个等），补充具体指代对象
2. 保留原意，不要添加新信息
3. 只输出改写后的查询，不要任何解释

对话历史：
{history_text}

用户最新问题：{question}

改写后的查询："""

        llm = _mm.get_active_llm()
        result = await llm.chat([
            {"role": "system", "content": "你是一个查询改写助手，擅长结合对话上下文改写搜索查询。"},
            {"role": "user", "content": prompt},
        ])
        rewritten = (result.get("content", "") or "").strip().strip('"').strip("'")
        # 如果改写结果为空或过长（异常），回退到原问题
        if not rewritten:
            logger.warning(f"[rewrite] 改写结果为空，回退到原问题 skill_id={getattr(skill, 'id', '?')} question='{question[:80]}'")
            rewritten = question
        elif len(rewritten) > len(question) * 5:
            logger.warning(f"[rewrite] 改写结果异常过长({len(rewritten)}字符)，回退到原问题 skill_id={getattr(skill, 'id', '?')} question='{question[:80]}'")
            rewritten = question
        else:
            logger.info(f"[rewrite] skill_id={getattr(skill, 'id', '?')} '{question[:50]}' → '{rewritten[:50]}'")
            # 仅在改写结果有效时写入缓存（异常回退的不缓存）
            rewrite_cache.set(question, history or [], rewritten)
        return rewritten, {
            "original": question,
            "rewritten": rewritten,
            "tokens": result.get("input_tokens", 0) + result.get("output_tokens", 0),
            "cache_hit": False,
        }

    def _filter_by_relevance(self, results: list, degraded: bool) -> tuple:
        """相似度阈值过滤：丢弃低于阈值的低质量结果

        Args:
            results: 检索结果列表
            degraded: 是否为降级模式（无 Embedding，仅 BM25）

        Returns:
            tuple: (过滤后的结果列表, 是否低置信度)
            - 低置信度 = 过滤后结果为空，或 top-1 分数低于阈值
        """
        from app.config import RAG_RELEVANCE_THRESHOLD

        if not results:
            return [], True

        # 降级模式下 BM25 结果 score=0，不做阈值过滤，仅标记低置信度
        if degraded:
            return results, True

        # 过滤低分结果
        filtered = [r for r in results if r.get("score", 0.0) >= RAG_RELEVANCE_THRESHOLD]

        # 如果过滤后为空，但原始有结果，保留 top-1（避免完全没有上下文）
        if not filtered and results:
            filtered = [results[0]]

        # 低置信度判断：top-1 分数低于阈值
        top_score = filtered[0].get("score", 0.0) if filtered else 0.0
        low_confidence = top_score < RAG_RELEVANCE_THRESHOLD

        return filtered, low_confidence

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

        # 4. 为 BM25 命中但向量未命中的 knowledge 批量补充 chunk（K-5: 避免 N+1 查询）
        missing_kids = [kid for kid in bm25_kids if kid not in kid_to_chunk]
        if missing_kids:
            batch_chunks = vector_store.get_batch_by_knowledge_ids(missing_kids, limit_per_kid=1)
            for kid, chunks in batch_chunks.items():
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

        # 状态过滤：仅检索 published 状态的知识（draft/archived 不可见）
        q = q.filter(Knowledge.status == "published")

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
            esc_kw = kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(Knowledge.title.like(f"%{esc_kw}%", escape="\\"))
            conditions.append(Knowledge.content.like(f"%{esc_kw}%", escape="\\"))

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
