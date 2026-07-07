"""Skill 选项路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.skill_option import SkillOptionCreate, SkillOptionUpdate
from app.services import skill_option_service
from app.utils.response import success

router = APIRouter()


@router.get("")
def list_options(type: str = None, db: Session = Depends(get_db)):
    """获取分类/功能选项列表"""
    items = skill_option_service.get_list(db, opt_type=type)
    return success(items)


@router.post("")
def create_option(data: SkillOptionCreate, db: Session = Depends(get_db)):
    """创建选项"""
    o = skill_option_service.create(db, data)
    return success(skill_option_service._to_out(o), message="创建成功")


@router.put("/{oid}")
def update_option(oid: int, data: SkillOptionUpdate, db: Session = Depends(get_db)):
    """更新选项"""
    o = skill_option_service.update(db, oid, data)
    return success(skill_option_service._to_out(o), message="更新成功")


@router.delete("/{oid}")
def delete_option(oid: int, db: Session = Depends(get_db)):
    """删除选项"""
    skill_option_service.delete(db, oid)
    return success(message="删除成功")
