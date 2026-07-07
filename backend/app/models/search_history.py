"""搜索历史模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String

from app.database import Base


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(500), nullable=False, comment="搜索词")
    search_type = Column(String(20), default="semantic", comment="搜索类型: semantic/keyword")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
