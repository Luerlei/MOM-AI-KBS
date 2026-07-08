"""时序预测数据集模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class Dataset(Base):
    """时序预测数据集

    series_data 存储格式（JSON 字符串）:
        [{"time": "2024-01", "value": 120.5, "label": ""}, ...]

    time: 时间标签（字符串，支持多种格式：2024-01 / 2024-01-15 / 2024 / t1 等）
    value: 观测值（数值）
    label: 数据点标注（可选，如"促销月"、"异常"）
    """
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="数据集名称")
    description = Column(Text, default="", comment="描述")
    frequency = Column(String(20), default="other", comment="数据频率: daily/weekly/monthly/quarterly/yearly/hourly/other")
    unit = Column(String(50), default="", comment="单位")
    series_data = Column(Text, default="[]", comment="数据点 JSON: [{time, value, label}]")
    point_count = Column(Integer, default=0, comment="数据点数")
    source = Column(String(20), default="manual", comment="来源: excel/manual/seed")
    source_file = Column(String(255), default="", comment="导入文件名")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())
