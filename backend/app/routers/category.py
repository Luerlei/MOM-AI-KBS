"""分类管理路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Knowledge
from app.schemas.knowledge import CategoryCreate, CategoryOut
from app.utils.response import success, APIError

router = APIRouter()


def _build_tree(categories: list, parent_id=None) -> list:
    """递归构建分类树"""
    out = []
    for c in categories:
        if c.parent_id == parent_id:
            node = {
                "id": c.id,
                "name": c.name,
                "parent_id": c.parent_id,
                "sort_order": c.sort_order,
                "created_at": c.created_at,
                "children": _build_tree(categories, c.id),
            }
            out.append(node)
    return out


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    """分类树（递归构建 children）"""
    categories = db.query(Category).order_by(Category.sort_order, Category.id).all()
    tree = _build_tree(categories)
    return success(tree)


@router.post("")
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    """创建分类"""
    c = Category(name=data.name, parent_id=data.parent_id, sort_order=data.sort_order)
    db.add(c)
    db.commit()
    db.refresh(c)
    return success({
        "id": c.id, "name": c.name, "parent_id": c.parent_id,
        "sort_order": c.sort_order, "created_at": c.created_at, "children": [],
    }, message="创建成功")


@router.put("/{cid}")
def update_category(cid: int, data: CategoryCreate, db: Session = Depends(get_db)):
    """更新分类"""
    c = db.query(Category).filter(Category.id == cid).first()
    if not c:
        raise APIError("分类不存在", status_code=404)
    # 防止将父分类设为自己
    if data.parent_id == cid:
        raise APIError("不能将自身设为父分类")
    c.name = data.name
    c.parent_id = data.parent_id
    c.sort_order = data.sort_order
    db.commit()
    db.refresh(c)
    return success({
        "id": c.id, "name": c.name, "parent_id": c.parent_id,
        "sort_order": c.sort_order, "created_at": c.created_at,
    }, message="更新成功")


@router.delete("/{cid}")
def delete_category(cid: int, db: Session = Depends(get_db)):
    """删除分类（如果含知识则提示）"""
    c = db.query(Category).filter(Category.id == cid).first()
    if not c:
        raise APIError("分类不存在", status_code=404)
    # 检查是否有知识条目
    count = db.query(Knowledge).filter(Knowledge.category_id == cid).count()
    if count > 0:
        raise APIError(f"该分类下有 {count} 条知识，请先迁移后再删除")
    # 检查子分类
    children = db.query(Category).filter(Category.parent_id == cid).count()
    if children > 0:
        raise APIError("该分类含有子分类，请先删除子分类")
    db.delete(c)
    db.commit()
    return success(message="删除成功")
