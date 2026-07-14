"""会话模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table
from sqlalchemy.orm import relationship

from app.database import Base

# 会话-知识库多对多关联表
conversation_knowledge_bases = Table(
    "conversation_knowledge_bases",
    Base.metadata,
    Column("conversation_id", Integer, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True),
    Column("knowledge_base_id", Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True),
)


class Conversation(Base):
    """会话：管理多轮对话上下文 + 知识库范围

    会话内问答只检索关联的知识库，不走 Skill 路由。
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="会话标题")
    description = Column(Text, default="", comment="会话描述")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())

    # 关联知识库（多对多）
    knowledge_bases = relationship("KnowledgeBase", secondary=conversation_knowledge_bases)
    # 会话消息（一对多）
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.id")


class ConversationMessage(Base):
    """会话消息：单条问答记录"""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, comment="所属会话")
    role = Column(String(20), nullable=False, comment="角色: user/assistant")
    content = Column(Text, default="", comment="消息内容")
    sources_json = Column(Text, default="[]", comment="引用来源 JSON")
    token_input = Column(Integer, default=0, comment="输入 token 数")
    token_output = Column(Integer, default=0, comment="输出 token 数")
    duration_ms = Column(Integer, default=0, comment="耗时毫秒")
    model_name = Column(String(100), nullable=True, comment="使用的模型名称")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    conversation = relationship("Conversation", back_populates="messages")
