"""知识条目模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table
from sqlalchemy.orm import relationship

from app.database import Base

# 知识-标签多对多关联表
knowledge_tags = Table(
    "knowledge_tags",
    Base.metadata,
    Column("knowledge_id", Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Knowledge(Base):
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=False, default="", comment="内容（Markdown）")
    content_type = Column(String(50), default="标准文档", comment="类型：标准文档/经验知识/培训资料/数据报表")
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, comment="分类目录")
    source_type = Column(String(20), default="manual", comment="来源：upload/manual")
    source_file = Column(String(255), nullable=True, comment="原始文件名")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())

    category = relationship("Category")
    tags = relationship("Tag", secondary=knowledge_tags)
    documents = relationship("Document", back_populates="knowledge", cascade="all, delete-orphan")


class KnowledgeTag(Base):
    __tablename__ = "knowledge_tag_relation"
    knowledge_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
