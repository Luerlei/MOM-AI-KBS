"""Token消耗记录模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey

from app.database import Base


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    call_type = Column(String(30), nullable=False, comment="调用类型: chat/embedding/summary")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    input_tokens = Column(Integer, default=0, comment="输入token")
    output_tokens = Column(Integer, default=0, comment="输出token")
    duration_ms = Column(Integer, default=0, comment="耗时毫秒")
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, comment="关联Skill")
    qa_history_id = Column(Integer, ForeignKey("qa_history.id", ondelete="SET NULL"), nullable=True, comment="关联问答记录")
    source = Column(String(50), default="qa", comment="发起来源: qa(智能问答)/chat(浮窗对话)/search(搜索)/internal(内部)")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
