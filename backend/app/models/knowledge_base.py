"""知识库模型（顶层容器）"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class KnowledgeBase(Base):
    """知识库：顶层容器，管理一组知识条目和模型配置

    每个知识库可独立配置 LLM/Embedding/Rerank/OCR/VLM，
    为 NULL 时继承全局 ModelConfig 配置。
    """
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="知识库名称")
    description = Column(Text, default="", comment="知识库描述")
    # 模型配置（nullable，为空时继承全局配置）
    llm_config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, comment="LLM 配置（空则继承全局）")
    embedding_config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, comment="Embedding 配置（空则继承全局）")
    rerank_config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, comment="Rerank 配置（空则继承全局）")
    ocr_config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, comment="OCR 配置（空则继承全局）")
    vlm_config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, comment="VLM 配置（空则继承全局）")
    # 上传解析开关：true=上传时立即解析，false=仅上传待手动解析
    parse_on_upload = Column(Boolean, default=True, comment="上传时是否立即解析")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())

    # 关联配置对象（不级联删除，避免删知识库时把全局模型配置也删了）
    llm_config = relationship("ModelConfig", foreign_keys=[llm_config_id])
    embedding_config = relationship("ModelConfig", foreign_keys=[embedding_config_id])
    rerank_config = relationship("ModelConfig", foreign_keys=[rerank_config_id])
    ocr_config = relationship("ModelConfig", foreign_keys=[ocr_config_id])
    vlm_config = relationship("ModelConfig", foreign_keys=[vlm_config_id])
