"""知识状态变更审计日志模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class KnowledgeStatusLog(Base):
    __tablename__ = "knowledge_status_log"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(Integer, nullable=False, index=True, comment="知识 ID")
    knowledge_title = Column(String(500), comment="知识标题（变更时快照）")
    old_status = Column(String(20), comment="旧状态: draft/published/archived")
    new_status = Column(String(20), comment="新状态: draft/published/archived")
    operator = Column(String(100), default="system", comment="操作人（用户名或 system）")
    reason = Column(Text, nullable=True, comment="变更原因（可选）")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat(), comment="变更时间")
