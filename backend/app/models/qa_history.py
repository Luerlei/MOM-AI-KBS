"""问答历史模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey

from app.database import Base


class QAHistory(Base):
    __tablename__ = "qa_history"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, nullable=False, default="", comment="AI答案")
    sources = Column(Text, default="[]", comment="来源标注 JSON")
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, comment="匹配的Skill")
    skill_name = Column(String(100), nullable=True, comment="Skill名称快照")
    feedback = Column(Integer, nullable=True, comment="反馈: 1=有用, -1=无用, null=未反馈")
    token_input = Column(Integer, default=0, comment="输入token")
    token_output = Column(Integer, default=0, comment="输出token")
    duration_ms = Column(Integer, default=0, comment="耗时毫秒")
    is_cache_hit = Column(Integer, default=0, comment="N10: 是否缓存命中: 0=否, 1=是")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
