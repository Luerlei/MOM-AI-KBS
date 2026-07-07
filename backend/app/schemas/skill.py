"""Skill Pydantic模型"""
from typing import Optional, List
from pydantic import BaseModel


class SkillBase(BaseModel):
    name: str
    description: str = ""
    category: str = "通用"
    function: str = "通用问答"
    trigger_keywords: List[str] = []
    trigger_patterns: List[str] = []
    prompt_template: str = ""
    knowledge_scope: dict = {}
    enabled: bool = True


class SkillCreate(SkillBase):
    is_default: bool = False


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    function: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    trigger_patterns: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    knowledge_scope: Optional[dict] = None
    enabled: Optional[bool] = None


class SkillOut(SkillBase):
    id: int
    is_default: bool

    class Config:
        from_attributes = True


class SkillTestRequest(BaseModel):
    question: str


class SkillTestResult(BaseModel):
    matched_skill: Optional[SkillOut] = None
    match_type: str = ""  # keyword / semantic / default
    score: float = 0.0
    all_scores: List[dict] = []
