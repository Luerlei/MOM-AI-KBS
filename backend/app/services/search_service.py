"""搜索服务"""
import logging
import os
from typing import Optional

from sqlalchemy.orm import joinedload

from app.models import Knowledge, Tag
from app.models.knowledge import knowledge_tags
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


async def semantic_search(db, query: str, category_id: Optional[int] = None,
                    tag_ids: Optional[list] = None,
                    date_from: Optional[str] = None, date_to: Optional[str] = None,
                    page: int = 1, page_size: int = 10):
    """语义搜索"""
    # 1. 向量化查询
    vecs = await embedding_service.embed([query], source="search")
    if not vecs:
        return [], 0
    q_vec = vecs[0]

    # 2. ChromaDB 检索（多检索一些再过滤）
    where = None
    if category_id:
        where = {"category_id": str(category_id)}
    raw_results = vector_store.search(query_embedding=q_vec, where=where, top_k=page * page_size * 2)

    # 3. 收集所有 knowledge_id，批量查询（修复 N+1）
    kid_to_results = {}
    for r in raw_results:
        kid = r.get("metadata", {}).get("knowledge_id")
        if kid:
            kid_to_results.setdefault(kid, []).append(r)

    all_kids = [int(k) for k in kid_to_results.keys()]
    knowledge_map = {}
    if all_kids:
        # 使用 joinedload 避免 N+1 懒加载（category + tags）
        k_list = (
            db.query(Knowledge)
            .options(joinedload(Knowledge.category), joinedload(Knowledge.tags))
            .filter(Knowledge.id.in_(all_kids))
            .all()
        )
        knowledge_map = {k.id: k for k in k_list}

    # 4. 按 tag_ids 过滤（应用层，使用批量查询的结果）
    if tag_ids:
        filtered_kids = []
        for kid in kid_to_results.keys():
            k = knowledge_map.get(int(kid))
            if k and any(t.id in tag_ids for t in k.tags):
                filtered_kids.append(kid)
        kid_to_results = {k: kid_to_results[k] for k in filtered_kids}

    # 4b. 按时间范围过滤
    if date_from or date_to:
        filtered_kids = []
        for kid in kid_to_results.keys():
            k = knowledge_map.get(int(kid))
            if k and _in_time_range(k.created_at, date_from, date_to):
                filtered_kids.append(kid)
        kid_to_results = {k: kid_to_results[k] for k in filtered_kids}

    # 5. 去重（每个 knowledge_id 取第一个 chunk）+ 组装
    dedup = []
    seen_kids = set()
    for r in raw_results:
        kid = r.get("metadata", {}).get("knowledge_id")
        if kid and kid not in seen_kids and kid in kid_to_results:
            seen_kids.add(kid)
            dedup.append(r)

    total = len(dedup)
    start_idx = (page - 1) * page_size
    page_items = dedup[start_idx:start_idx + page_size]

    # 6. 组装结果（使用批量查询的 knowledge_map）
    results = []
    for r in page_items:
        meta = r.get("metadata", {})
        kid = int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0
        k = knowledge_map.get(kid)
        results.append({
            "id": kid,
            "knowledge_id": kid,
            "title": k.title if k else meta.get("title", ""),
            "snippet": (r.get("document", "") or "")[:200],
            "score": r.get("score", 0.0),
            "content_type": k.content_type if k else "",
            "category_name": k.category.name if k and k.category else None,
            "tags": [{"id": t.id, "name": t.name, "color": getattr(t, "color", None)} for t in k.tags] if k else [],
            "tag_names": [t.name for t in k.tags] if k else [],
        })
    return results, total


def keyword_search(db, query: str, category_id: Optional[int] = None,
                   tag_ids: Optional[list] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   page: int = 1, page_size: int = 10):
    """关键词搜索（SQLite LIKE + jieba 中文分词）"""
    from sqlalchemy import or_
    from app.services.rag_service import _tokenize_keywords

    q = db.query(Knowledge).options(joinedload(Knowledge.category), joinedload(Knowledge.tags))
    if category_id:
        q = q.filter(Knowledge.category_id == category_id)
    if tag_ids:
        q = q.join(knowledge_tags).join(Tag).filter(Tag.id.in_(tag_ids)).distinct()

    # 中文分词：对每个关键词构建 OR 条件（标题命中 OR 内容命中）
    keywords = _tokenize_keywords(query)
    if keywords:
        conditions = []
        for kw in keywords:
            conditions.append(Knowledge.title.like(f"%{kw}%"))
            conditions.append(Knowledge.content.like(f"%{kw}%"))
        q = q.filter(or_(*conditions))
    else:
        # 回退：整句子串匹配（单字符查询或纯标点）
        q = q.filter(Knowledge.title.like(f"%{query}%") | Knowledge.content.like(f"%{query}%"))

    if date_from:
        q = q.filter(Knowledge.created_at >= date_from)
    if date_to:
        # created_at 存储为 ISO 格式（T 分隔符），用 T23:59:59 避免当天数据丢失
        q = q.filter(Knowledge.created_at <= date_to + "T23:59:59")
    total = q.count()
    items = q.order_by(Knowledge.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for k in items:
        # 计算 snippet：优先展示首个关键词的命中位置
        content = k.content or ""
        snippet_kw = query
        idx = -1
        if keywords:
            for kw in keywords:
                pos = content.find(kw)
                if pos >= 0:
                    snippet_kw = kw
                    idx = pos
                    break
        else:
            idx = content.find(query)
        if idx >= 0:
            start = max(0, idx - 50)
            snippet = content[start:start + 200]
        else:
            snippet = content[:200]

        # 评分：标题命中权重 2，内容命中权重 1（按关键词匹配数累加）
        score = 0.0
        if keywords:
            for kw in keywords:
                if kw in (k.title or ""):
                    score += 2.0
                if kw in content:
                    score += 1.0
        else:
            score = 2.0 if (idx >= 0) else 0.5

        results.append({
            "id": k.id,
            "knowledge_id": k.id,
            "title": k.title,
            "snippet": snippet,
            "score": score,
            "content_type": k.content_type,
            "category_name": k.category.name if k.category else None,
            "tags": [{"id": t.id, "name": t.name, "color": getattr(t, "color", None)} for t in k.tags],
            "tag_names": [t.name for t in k.tags],
        })
    return results, total


def _in_time_range(created_at: str, date_from: Optional[str], date_to: Optional[str]) -> bool:
    """判断时间是否在范围内（字符串比较，兼容 ISO 格式）

    注意：created_at 存储为 ISO 格式（T 分隔符，如 "2026-07-12T10:30:00"），
    date_to 必须用 T23:59:59 才能包含当天数据（空格 ASCII 0x20 < T 0x54）。
    """
    if not created_at:
        return True
    if date_from and created_at < date_from:
        return False
    if date_to and created_at > date_to + "T23:59:59":
        return False
    return True


def save_search_history(db, query: str, search_type: str):
    """保存搜索历史"""
    from app.models import SearchHistory
    h = SearchHistory(query=query[:500], search_type=search_type)
    db.add(h)
    db.commit()


def get_search_history(db, limit: int = 20) -> list:
    """获取搜索历史"""
    from app.models import SearchHistory
    items = db.query(SearchHistory).order_by(SearchHistory.created_at.desc()).limit(limit).all()
    return [{"id": h.id, "query": h.query, "search_type": h.search_type, "created_at": h.created_at} for h in items]
