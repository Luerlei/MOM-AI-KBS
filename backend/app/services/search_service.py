"""搜索服务"""
import os
from typing import Optional

from app.models import Knowledge, Tag
from app.models.knowledge import knowledge_tags
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.knowledge_service import _run_async


def semantic_search(db, query: str, category_id: Optional[int] = None,
                    tag_ids: Optional[list] = None,
                    date_from: Optional[str] = None, date_to: Optional[str] = None,
                    page: int = 1, page_size: int = 10):
    """语义搜索"""
    # 1. 向量化查询
    vecs = _run_async(embedding_service.embed([query], source="search"))
    if not vecs:
        return [], 0
    q_vec = vecs[0]

    # 2. ChromaDB 检索（多检索一些再过滤）
    where = None
    if category_id:
        where = {"category_id": str(category_id)}
    raw_results = vector_store.search(query_embedding=q_vec, where=where, top_k=page * page_size * 2)

    # 3. 按 tag_ids 过滤（应用层）
    if tag_ids:
        filtered = []
        for r in raw_results:
            kid = r.get("metadata", {}).get("knowledge_id")
            if kid:
                k = db.query(Knowledge).filter(Knowledge.id == int(kid)).first()
                if k and any(t.id in tag_ids for t in k.tags):
                    filtered.append(r)
        raw_results = filtered

    # 3b. 按时间范围过滤（应用层）
    if date_from or date_to:
        filtered = []
        for r in raw_results:
            kid = r.get("metadata", {}).get("knowledge_id")
            if kid:
                k = db.query(Knowledge).filter(Knowledge.id == int(kid)).first()
                if k and _in_time_range(k.created_at, date_from, date_to):
                    filtered.append(r)
        raw_results = filtered

    # 4. 去重 + 组装
    seen_kids = set()
    dedup = []
    for r in raw_results:
        kid = r.get("metadata", {}).get("knowledge_id")
        if kid and kid not in seen_kids:
            seen_kids.add(kid)
            dedup.append(r)

    total = len(dedup)
    start_idx = (page - 1) * page_size
    page_items = dedup[start_idx:start_idx + page_size]

    # 5. 组装结果
    results = []
    for r in page_items:
        meta = r.get("metadata", {})
        kid = int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0
        k = db.query(Knowledge).filter(Knowledge.id == kid).first() if kid else None
        results.append({
            "knowledge_id": kid,
            "title": k.title if k else meta.get("title", ""),
            "snippet": (r.get("document", "") or "")[:200],
            "score": r.get("score", 0.0),
            "content_type": k.content_type if k else "",
            "category_name": k.category.name if k and k.category else None,
            "tag_names": [t.name for t in k.tags] if k else [],
        })
    return results, total


def keyword_search(db, query: str, category_id: Optional[int] = None,
                   tag_ids: Optional[list] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   page: int = 1, page_size: int = 10):
    """关键词搜索（SQLite LIKE）"""
    q = db.query(Knowledge)
    if category_id:
        q = q.filter(Knowledge.category_id == category_id)
    if tag_ids:
        q = q.join(knowledge_tags).join(Tag).filter(Tag.id.in_(tag_ids))
    q = q.filter(Knowledge.title.like(f"%{query}%") | Knowledge.content.like(f"%{query}%"))
    if date_from:
        q = q.filter(Knowledge.created_at >= date_from)
    if date_to:
        q = q.filter(Knowledge.created_at <= date_to + " 23:59:59")
    total = q.count()
    items = q.order_by(Knowledge.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for k in items:
        # 计算 snippet
        content = k.content or ""
        idx = content.find(query)
        if idx >= 0:
            start = max(0, idx - 50)
            snippet = content[start:start + 200]
        else:
            snippet = content[:200]
        results.append({
            "knowledge_id": k.id,
            "title": k.title,
            "snippet": snippet,
            "score": 1.0 if idx >= 0 else 0.5,
            "content_type": k.content_type,
            "category_name": k.category.name if k.category else None,
            "tag_names": [t.name for t in k.tags],
        })
    return results, total


def _in_time_range(created_at: str, date_from: Optional[str], date_to: Optional[str]) -> bool:
    """判断时间是否在范围内（字符串比较，兼容 ISO 格式）"""
    if not created_at:
        return True
    if date_from and created_at < date_from:
        return False
    if date_to and created_at > date_to + " 23:59:59":
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
