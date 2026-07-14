"""知识库管理 Pydantic 模型"""
from typing import Optional, List
from pydantic import BaseModel


class KnowledgeBaseCreate(BaseModel):
    """创建知识库"""
    name: str
    description: str = ""
    llm_config_id: Optional[int] = None
    embedding_config_id: Optional[int] = None
    rerank_config_id: Optional[int] = None
    ocr_config_id: Optional[int] = None
    vlm_config_id: Optional[int] = None
    parse_on_upload: bool = True


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库"""
    name: Optional[str] = None
    description: Optional[str] = None
    llm_config_id: Optional[int] = None
    embedding_config_id: Optional[int] = None
    rerank_config_id: Optional[int] = None
    ocr_config_id: Optional[int] = None
    vlm_config_id: Optional[int] = None
    parse_on_upload: Optional[bool] = None


class KnowledgeBaseOut(BaseModel):
    """知识库输出"""
    id: int
    name: str
    description: str = ""
    llm_config_id: Optional[int] = None
    embedding_config_id: Optional[int] = None
    rerank_config_id: Optional[int] = None
    ocr_config_id: Optional[int] = None
    vlm_config_id: Optional[int] = None
    parse_on_upload: bool = True
    # 关联模型名称（便于前端展示）
    llm_model_name: Optional[str] = None
    embedding_model_name: Optional[str] = None
    rerank_model_name: Optional[str] = None
    ocr_model_name: Optional[str] = None
    vlm_model_name: Optional[str] = None
    # 统计信息
    document_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
