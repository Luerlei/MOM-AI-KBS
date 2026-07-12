"""数据集协变量模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class DatasetCovariate(Base):
    """数据集协变量

    用于支持时序预测中的外生变量（exogenous variables）。

    values_json 存储格式（与主数据时间轴对齐）:
        [{"time": "2024-01", "value": 1}, {"time": "2024-02", "value": 0}, ...]

    type 取值:
        continuous: 连续型（如温度、价格）
        binary: 二元型（如是否节假日、是否促销）
        categorical: 分类型（如季节，需用户自行编码为数值）

    source_type 取值:
        manual: 用户手动创建
        auto: 系统自动生成（工作日/节假日/趋势/周期）
        template: 从模板应用
    """
    __tablename__ = "dataset_covariates"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, nullable=False, index=True, comment="关联数据集ID")
    name = Column(String(100), nullable=False, comment="协变量名称（如 节假日）")
    code = Column(String(50), nullable=False, comment="英文标识（如 is_holiday），用作 exog 列名")
    type = Column(String(20), default="continuous", comment="类型: continuous/binary/categorical")
    source_type = Column(String(20), default="manual", comment="来源: manual/auto/template")
    values_json = Column(Text, default="[]", comment="协变量值 JSON: [{time, value}]")
    description = Column(String(500), default="", comment="备注说明")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(),
                        onupdate=lambda: datetime.utcnow().isoformat())
