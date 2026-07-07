"""标签管理路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tag
from app.schemas.knowledge import TagCreate
from app.utils.response import success, APIError

router = APIRouter()


@router.get("")
def list_tags(db: Session = Depends(get_db)):
    """标签列表"""
    tags = db.query(Tag).order_by(Tag.id).all()
    return success([{"id": t.id, "name": t.name} for t in tags])


@router.post("")
def create_tag(data: TagCreate, db: Session = Depends(get_db)):
    """创建标签"""
    existing = db.query(Tag).filter(Tag.name == data.name).first()
    if existing:
        raise APIError("标签已存在")
    t = Tag(name=data.name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return success({"id": t.id, "name": t.name}, message="创建成功")


@router.delete("/{tid}")
def delete_tag(tid: int, db: Session = Depends(get_db)):
    """删除标签"""
    t = db.query(Tag).filter(Tag.id == tid).first()
    if not t:
        raise APIError("标签不存在", status_code=404)
    db.delete(t)
    db.commit()
    return success(message="删除成功")
