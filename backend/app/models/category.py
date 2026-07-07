"""分类目录模型（树形结构）"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="分类名称")
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, comment="父分类ID")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    parent = relationship("Category", remote_side=[id], backref="children")
