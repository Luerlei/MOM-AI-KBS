"""Skill模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean

from app.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="Skill名称")
    description = Column(Text, nullable=False, default="", comment="描述")
    category = Column(String(50), nullable=False, default="通用", comment="模块维度：制造运营/仓储物流/质量管理/设备管理/通用")
    function = Column(String(50), nullable=False, default="通用问答", comment="功能维度：故障诊断/保养维护/工艺指导/质量检验等")
    trigger_keywords = Column(Text, default="[]", comment='触发关键词列表 JSON: ["故障","报错"]')
    trigger_patterns = Column(Text, default="[]", comment='触发模式(正则) JSON: ["E\\d+"]')
    prompt_template = Column(Text, nullable=False, default="", comment="Prompt模板，含{context}{question}变量")
    knowledge_scope = Column(Text, default="{}", comment='知识范围 JSON: {"category_ids":[],"tag_ids":[]}')
    enabled = Column(Boolean, default=True, comment="启用状态")
    is_default = Column(Boolean, default=False, comment="是否默认Skill")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())
