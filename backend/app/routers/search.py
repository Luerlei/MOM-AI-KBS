"""搜索路由"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import search_service
from app.utils.response import success, page_result

router = APIRouter()


@router.get("/semantic")
def semantic_search(
    query: str,
    category_id: Optional[int] = None,
    tag_ids: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    """语义搜索"""
    tag_id_list = None
    if tag_ids:
        try:
            tag_id_list = [int(x) for x in tag_ids.split(",") if x.strip()]
        except ValueError:
            tag_id_list = None
    results, total = search_service.semantic_search(
        db, query=query, category_id=category_id, tag_ids=tag_id_list,
        date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )
    # 保存搜索历史
    try:
        search_service.save_search_history(db, query, "semantic")
    except Exception:
        pass
    return page_result(results, total, page, page_size)


@router.get("/keyword")
def keyword_search(
    query: str,
    category_id: Optional[int] = None,
    tag_ids: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    """关键词搜索"""
    tag_id_list = None
    if tag_ids:
        try:
            tag_id_list = [int(x) for x in tag_ids.split(",") if x.strip()]
        except ValueError:
            tag_id_list = None
    results, total = search_service.keyword_search(
        db, query=query, category_id=category_id, tag_ids=tag_id_list,
        date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )
    try:
        search_service.save_search_history(db, query, "keyword")
    except Exception:
        pass
    return page_result(results, total, page, page_size)


@router.get("/history")
def search_history(limit: int = 20, db: Session = Depends(get_db)):
    """搜索历史"""
    items = search_service.get_search_history(db, limit=limit)
    return success(items)
