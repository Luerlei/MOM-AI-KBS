"""标签模型"""
from sqlalchemy import Column, Integer, String

from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, comment="标签名")
    color = Column(String(20), nullable=True, default=None, comment="标签颜色")
