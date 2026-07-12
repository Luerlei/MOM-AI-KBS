"""知识管理 Pydantic模型"""
from typing import Optional, List
from pydantic import BaseModel


class KnowledgeBase(BaseModel):
    title: str
    content: str = ""
    content_type: str = "markdown"
    category_id: Optional[int] = None
    tag_ids: List[int] = []
    status: str = "published"  # draft(草稿) / published(发布) / archived(归档)


class KnowledgeCreate(KnowledgeBase):
    pass


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_type: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None
    status: Optional[str] = None  # draft / published / archived


class KnowledgeOut(BaseModel):
    id: int
    title: str
    content: str
    content_type: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    source_type: str
    source_file: Optional[str] = None
    status: str = "published"
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
    color: Optional[str] = None


class TagCreate(TagBase):
    pass


class TagOut(TagBase):
    id: int

    class Config:
        from_attributes = True


class BatchOperation(BaseModel):
    ids: List[int]
    action: str  # delete / add_tag(s) / move_category / set_category / set_status
    tag_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    status: Optional[str] = None  # set_status 时使用: draft / published / archived
