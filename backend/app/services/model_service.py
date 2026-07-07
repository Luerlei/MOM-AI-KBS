"""模型配置管理服务"""
import time

from app.models import ModelConfig
from app.schemas.model_config import ModelConfigCreate, ModelConfigUpdate, ModelTestResult
from app.utils.crypto import encrypt, decrypt, mask
from app.utils.response import APIError


def _to_out(config: ModelConfig) -> dict:
    """转输出格式（api_key 脱敏）"""
    return {
        "id": config.id,
        "name": config.name,
        "type": config.type,
        "api_url": config.api_url,
        "api_key_masked": mask(decrypt(config.api_key)),
        "model_name": config.model_name,
        "is_active": config.is_active,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


def get_list(db, type: str = None) -> list:
    """获取模型配置列表"""
    q = db.query(ModelConfig)
    if type:
        q = q.filter(ModelConfig.type == type)
    q = q.order_by(ModelConfig.type, ModelConfig.id)
    return [_to_out(c) for c in q.all()]


def get_by_id(db, id: int) -> ModelConfig:
    config = db.query(ModelConfig).filter(ModelConfig.id == id).first()
    if not config:
        raise APIError("模型配置不存在", status_code=404)
    return config


def create(db, data: ModelConfigCreate) -> ModelConfig:
    """创建模型配置"""
    config = ModelConfig(
        name=data.name,
        type=data.type,
        api_url=data.api_url,
        api_key=encrypt(data.api_key) if data.api_key else "",
        model_name=data.model_name,
        is_active=False,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    # 若标记为启用则激活
    if data.is_active:
        activate(db, config.id)
        db.refresh(config)
    return config


def update(db, id: int, data: ModelConfigUpdate) -> ModelConfig:
    """更新模型配置"""
    config = get_by_id(db, id)
    if data.name is not None:
        config.name = data.name
    if data.api_url is not None:
        config.api_url = data.api_url
    if data.api_key is not None:
        config.api_key = encrypt(data.api_key) if data.api_key else ""
    if data.model_name is not None:
        config.model_name = data.model_name
    db.commit()
    db.refresh(config)
    if data.is_active:
        activate(db, config.id)
        db.refresh(config)
    return config


def delete(db, id: int):
    """删除模型配置（启用中的不允许删除）"""
    config = get_by_id(db, id)
    if config.is_active:
        raise APIError("该模型配置当前已启用，请先切换到其他配置后再删除", status_code=400)
    db.delete(config)
    db.commit()


def activate(db, id: int):
    """启用某配置（同类型其他配置设为未启用）"""
    config = get_by_id(db, id)
    db.query(ModelConfig).filter(
        ModelConfig.type == config.type, ModelConfig.is_active == True  # noqa: E712
    ).update({ModelConfig.is_active: False})
    config.is_active = True
    db.commit()
    db.refresh(config)
    return config


async def test_connection(db, id: int) -> ModelTestResult:
    """测试模型连通性，发送简单请求测量延迟

    每次测试都会记录 TokenUsage 日志（call_type=test, source=test_model）
    """
    config = get_by_id(db, id)
    from app.services.llm_client import OpenAICompatibleClient

    client = OpenAICompatibleClient(config)
    start = time.time()
    try:
        if config.type == "LLM":
            result = await client.chat([{"role": "user", "content": "ping"}])
            latency = int((time.time() - start) * 1000)
            usage = getattr(client, "last_usage", {}) or {}
            _log_test_usage(
                db, config,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                latency_ms=latency,
            )
            return ModelTestResult(
                success=True,
                message=f"连接成功，模型: {result.get('model', config.model_name)}",
                latency_ms=latency,
            )
        else:  # Embedding
            vec = await client.embedding(["ping"])
            latency = int((time.time() - start) * 1000)
            dim = len(vec[0]) if vec and vec[0] else 0
            usage = getattr(client, "last_usage", {}) or {}
            _log_test_usage(
                db, config,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=0,
                latency_ms=latency,
            )
            return ModelTestResult(
                success=True,
                message=f"连接成功，向量维度: {dim}",
                latency_ms=latency,
            )
    except APIError:
        latency = int((time.time() - start) * 1000)
        _log_test_usage(db, config, input_tokens=0, output_tokens=0, latency_ms=latency, success=False)
        raise
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        _log_test_usage(db, config, input_tokens=0, output_tokens=0, latency_ms=latency, success=False)
        return ModelTestResult(
            success=False,
            message=f"连接失败: {str(e)}",
            latency_ms=latency,
        )


def _log_test_usage(db, config, input_tokens: int, output_tokens: int,
                   latency_ms: int, success: bool = True):
    """记录模型测试调用的 TokenUsage 日志"""
    try:
        from app.models import TokenUsage
        usage = TokenUsage(
            call_type="test",
            model_name=config.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=latency_ms,
            source="test_model",
        )
        db.add(usage)
        db.commit()
    except Exception:
        db.rollback()
