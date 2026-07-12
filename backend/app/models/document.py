"""上传文档记录模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="存储路径")
    file_type = Column(String(20), nullable=False, comment="pdf/docx/xlsx/md")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    file_hash = Column(String(64), nullable=True, index=True, comment="文件内容 SHA-256 哈希，用于去重")
    knowledge_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=True, comment="关联的知识条目")
    uploaded_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    knowledge = relationship("Knowledge", back_populates="documents")
