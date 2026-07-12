"""时序预测任务与结果模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey

from app.database import Base


class ForecastTask(Base):
    """预测任务

    记录每次预测执行的元信息与状态。
    同一数据集可多次评估，每次生成一条任务记录。
    """
    __tablename__ = "forecast_tasks"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联数据集")
    model_config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, comment="使用的 Forecast 模型配置")
    model_name = Column(String(100), default="", comment="实际使用的模型名称")
    horizon = Column(Integer, default=12, comment="预测步数")
    start_index = Column(Integer, nullable=True, default=None, comment="回测起点(从第几个点开始预测)，null=从末尾预测未来")
    status = Column(String(20), default="pending", comment="状态: pending/running/success/failed")
    error_message = Column(Text, default="", comment="失败原因")
    duration_ms = Column(Integer, default=0, comment="耗时(毫秒)")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    completed_at = Column(String, default="", comment="完成时间")
    is_internal = Column(Integer, default=0, comment="内部任务标记: 0=用户发起, 1=交叉验证/模型对比等内部回测")


class ForecastResult(Base):
    """预测结果

    存储预测输出（点预测 + 分位数预测 + 未来时间标签）。
    forecasts: [float, ...] 中位数点预测
    quantiles: {"0.1": [...], "0.5": [...], "0.9": [...]}
    future_times: ["2025-01", ...] 预测点对应的时间标签
    analysis: LLM 生成的自然语言分析报告
    """
    __tablename__ = "forecast_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("forecast_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True, comment="冗余便于查询")
    forecasts = Column(Text, default="[]", comment="点预测 JSON: [float]")
    quantiles = Column(Text, default="{}", comment="分位数预测 JSON: {str: [float]}")
    future_times = Column(Text, default="[]", comment="预测时间标签 JSON: [str]")
    actuals = Column(Text, default="[]", comment="回测实际值 JSON: [float]，仅回测模式有值")
    metrics = Column(Text, default="{}", comment="回测误差指标 JSON: {mae, mape, rmse}，仅回测模式有值")
    model_name = Column(String(100), default="", comment="实际使用的模型名称")
    analysis = Column(Text, default="", comment="LLM 生成的趋势分析报告")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
