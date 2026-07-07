"""模型配置 Pydantic模型"""
from typing import Optional
from pydantic import BaseModel


class ModelConfigBase(BaseModel):
    name: str
    type: str  # LLM / Embedding
    api_url: str
    api_key: str = ""
    model_name: str


class ModelConfigCreate(ModelConfigBase):
    is_active: bool = False


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None


class ModelConfigOut(BaseModel):
    id: int
    name: str
    type: str
    api_url: str
    api_key_masked: str = ""
    model_name: str
    is_active: bool

    class Config:
        from_attributes = True


class ModelTestResult(BaseModel):
    success: bool
    message: str = ""
    latency_ms: int = 0
