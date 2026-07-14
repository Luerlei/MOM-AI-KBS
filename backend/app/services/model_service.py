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
        "input_price": config.input_price or 0.0,
        "output_price": config.output_price or 0.0,
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
        input_price=data.input_price,
        output_price=data.output_price,
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
    if data.input_price is not None:
        config.input_price = data.input_price
    if data.output_price is not None:
        config.output_price = data.output_price
    db.commit()
    db.refresh(config)
    if data.is_active:
        activate(db, config.id)
        db.refresh(config)
    # 失效缓存（配置变更后旧客户端不再有效）
    from app.services.llm_client import model_manager
    model_manager.invalidate_cache(config.type)
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
    # 失效缓存（启用的配置变更）
    from app.services.llm_client import model_manager
    model_manager.invalidate_cache(config.type)
    return config


async def test_connection(db, id: int) -> ModelTestResult:
    """测试模型连通性，发送简单请求测量延迟

    每次测试都会记录 TokenUsage 日志（call_type=test, source=test_model）
    """
    config = get_by_id(db, id)
    from app.services.llm_client import OpenAICompatibleClient, ForecastClient, RerankClient

    start = time.time()
    try:
        if config.type in ("OCR", "VLM"):
            # OCR/VLM 是 vision 模型，纯文本 ping 通常返回 400/422（要求 image_url 输入）。
            # 2xx 和 400/422 都表示 API 可达且认证通过，算连通成功。
            # 401/403 表示认证失败，404 表示端点错误，5xx 表示服务异常。
            import httpx as _httpx
            from app.services.llm_client import _build_ssl_context
            from app.utils.crypto import decrypt
            api_url = config.api_url.rstrip("/")
            for suffix in ("/chat/completions", "/rerank", "/embeddings", "/predict"):
                if api_url.endswith(suffix):
                    api_url = api_url[: -len(suffix)]
                    break
            api_key = decrypt(config.api_key) if config.api_key else ""
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            try:
                async with _httpx.AsyncClient(timeout=30.0, verify=_build_ssl_context(), trust_env=False) as _http:
                    resp = await _http.post(
                        f"{api_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": config.model_name,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 5,
                        },
                    )
            except Exception as e:
                latency = int((time.time() - start) * 1000)
                _log_test_usage(db, config, 0, 0, latency_ms=latency, success=False)
                return ModelTestResult(
                    success=False,
                    message=f"连接失败（网络异常）: {type(e).__name__}: {str(e)[:150]}",
                    latency_ms=latency,
                )
            latency = int((time.time() - start) * 1000)
            # 2xx 成功
            if 200 <= resp.status_code < 300:
                _log_test_usage(db, config, 0, 0, latency_ms=latency)
                type_label = "VLM" if config.type == "VLM" else "OCR"
                return ModelTestResult(
                    success=True,
                    message=f"连接成功，{type_label} 模型: {config.model_name}",
                    latency_ms=latency,
                )
            # 400/422 表示 API 可达，只是输入格式不对（vision 模型需要图片/PDF）
            if resp.status_code in (400, 422):
                _log_test_usage(db, config, 0, 0, latency_ms=latency)
                type_label = "VLM" if config.type == "VLM" else "OCR"
                return ModelTestResult(
                    success=True,
                    message=f"API 可达，{type_label} 模型: {config.model_name}（纯文本 ping 返回 {resp.status_code} 属正常，需 PDF/图片输入）",
                    latency_ms=latency,
                )
            # 其他错误码
            body = resp.text[:200]
            _log_test_usage(db, config, 0, 0, latency_ms=latency, success=False)
            return ModelTestResult(
                success=False,
                message=f"连接失败({resp.status_code}): {body}",
                latency_ms=latency,
            )
        if config.type == "Rerank":
            # Rerank 模型：发送简单 rerank 请求测试连通性
            rr = RerankClient(config)
            ranked = await rr.rerank("test", ["文档内容A", "文档内容B"], top_n=2)
            latency = int((time.time() - start) * 1000)
            usage = getattr(rr, "last_usage", {}) or {}
            _log_test_usage(
                db, config,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=0,
                latency_ms=latency,
            )
            return ModelTestResult(
                success=True,
                message=f"连接成功，重排序返回 {len(ranked)} 条结果",
                latency_ms=latency,
            )
        if config.type == "Forecast":
            # 时序预测模型：发送短序列测试 /predict 端点
            client = ForecastClient(config)
            result = await client.predict(series=[1.0, 2.0, 3.0, 4.0, 5.0], horizon=2)
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
                message=f"连接成功，模型: {result.get('model', config.model_name)}，预测 {len(result.get('forecasts', []))} 步",
                latency_ms=latency,
            )
        # LLM / Embedding 走 OpenAI 兼容客户端
        client = OpenAICompatibleClient(config)
        if config.type == "LLM":
            # 流式请求测试连通性：收到 HTTP 200 响应头即确认
            # 思考模型（如 DeepSeek-V4-Flash）非流式需 >120s 会超时，流式只检查响应头
            import httpx as _httpx
            from app.services.llm_client import _build_ssl_context
            async with _httpx.AsyncClient(timeout=120.0, verify=_build_ssl_context(), trust_env=False) as _http:
                async with _http.stream(
                    "POST",
                    f"{client.api_url}/chat/completions",
                    headers=client._headers(),
                    json={
                        "model": config.model_name,
                        "messages": [{"role": "user", "content": "ping"}],
                        "stream": True,
                        "max_tokens": 5,
                    },
                ) as resp:
                    latency = int((time.time() - start) * 1000)
                    if resp.status_code != 200:
                        body = await resp.aread()
                        _log_test_usage(db, config, 0, 0, latency_ms=latency, success=False)
                        return ModelTestResult(
                            success=False,
                            message=f"连接失败({resp.status_code}): {body.decode('utf-8', errors='replace')[:200]}",
                            latency_ms=latency,
                        )
                    _log_test_usage(db, config, 0, 0, latency_ms=latency)
                    return ModelTestResult(
                        success=True,
                        message=f"连接成功，模型: {config.model_name}",
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
