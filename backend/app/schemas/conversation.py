"""会话管理 Pydantic 模型"""
from typing import Optional, List, Any
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    """创建会话"""
    title: str
    description: str = ""
    knowledge_base_ids: List[int] = []


class ConversationUpdate(BaseModel):
    """更新会话"""
    title: Optional[str] = None
    description: Optional[str] = None
    knowledge_base_ids: Optional[List[int]] = None


class ConversationMessageOut(BaseModel):
    """会话消息输出"""
    id: int
    conversation_id: int
    role: str
    content: str
    sources: List[Any] = []  # 引用来源列表（从 sources_json 解析）
    token_input: int = 0
    token_output: int = 0
    duration_ms: int = 0
    model_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    """会话输出"""
    id: int
    title: str
    description: str = ""
    knowledge_base_ids: List[int] = []
    knowledge_base_names: List[str] = []
    message_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ConversationDetailOut(ConversationOut):
    """会话详情（含消息历史）"""
    messages: List[ConversationMessageOut] = []


class ConversationAsk(BaseModel):
    """会话内提问"""
    question: str
    history_turns: int = 6  # 取最近 N 轮对话作为上下文
