"""模型配置模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float

from app.database import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="配置名称")
    type = Column(String(20), nullable=False, comment="模型类型: LLM / Embedding / Forecast / Rerank / OCR / VLM")
    api_url = Column(String(500), nullable=False, comment="API地址")
    api_key = Column(String(500), nullable=False, default="", comment="密钥（加密存储）")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    is_active = Column(Boolean, default=False, comment="是否启用（同类型仅一个启用）")
    input_price = Column(Float, default=0.0, comment="输入token单价（元/千token）")
    output_price = Column(Float, default=0.0, comment="输出token单价（元/千token）")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())
