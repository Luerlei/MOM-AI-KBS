"""Skill 选项 Pydantic模型"""
from typing import Optional
from pydantic import BaseModel


class SkillOptionBase(BaseModel):
    type: str  # category / function
    name: str
    description: str = ""
    sort_order: int = 0
    color: str = "default"


class SkillOptionCreate(SkillOptionBase):
    pass


class SkillOptionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    color: Optional[str] = None


class SkillOptionOut(SkillOptionBase):
    id: int

    class Config:
        from_attributes = True
