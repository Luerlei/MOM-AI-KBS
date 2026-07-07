"""Skill 选项模型（分类/功能的自定义可选项）"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class SkillOption(Base):
    """Skill 分类与功能维度的可配置选项

    type: "category" 模块维度 / "function" 功能维度
    name: 选项名称（如"设备管理"、"故障诊断"）
    """
    __tablename__ = "skill_options"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False, index=True, comment="category/function")
    name = Column(String(100), nullable=False, comment="选项名称")
    description = Column(Text, default="", comment="描述")
    sort_order = Column(Integer, default=0, comment="排序")
    color = Column(String(20), default="default", comment="标签颜色")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
