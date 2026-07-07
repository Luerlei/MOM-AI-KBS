"""知识管理 Pydantic模型"""
from typing import Optional, List
from pydantic import BaseModel


class KnowledgeBase(BaseModel):
    title: str
    content: str = ""
    content_type: str = "标准文档"
    category_id: Optional[int] = None
    tag_ids: List[int] = []


class KnowledgeCreate(KnowledgeBase):
    pass


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_type: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None


class KnowledgeOut(BaseModel):
    id: int
    title: str
    content: str
    content_type: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    source_type: str
    source_file: Optional[str] = None
    tag_ids: List[int] = []
    tag_names: List[str] = []
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int
    children: List["CategoryOut"] = []

    class Config:
        from_attributes = True


CategoryOut.model_rebuild()


class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class TagOut(TagBase):
    id: int

    class Config:
        from_attributes = True


class BatchOperation(BaseModel):
    ids: List[int]
    action: str  # delete / add_tag / move_category
    tag_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
