"""LLM 客户端抽象层（OpenAI 兼容格式）"""
import logging
import os
import ssl
import time
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator

import httpx

from app.utils.response import APIError

logger = logging.getLogger(__name__)


def _build_ssl_context() -> ssl.SSLContext:
    """构建 SSL 上下文。

    默认使用系统默认安全级别（不降低）。
    仅在环境变量 SSL_SECLEVEL=1 时回退到兼容模式（用于部分老服务商证书）。
    """
    ctx = ssl.create_default_context()
    if os.getenv("SSL_SECLEVEL", "") == "1":
        logger.warning("[security] SSL_SECLEVEL=1 已启用，降低了证书校验安全级别")
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    return ctx


class LLMClient(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> dict:
        """对话补全

        Returns:
            dict: {content, input_tokens, output_tokens, model}
        """
        pass

    @abstractmethod
    async def chat_stream(self, messages: list, **kwargs) -> AsyncGenerator[str, None]:
        """流式对话补全，逐步 yield 文本片段"""
        pass

    @abstractmethod
    async def embedding(self, texts: list) -> list:
        """向量化"""
        pass


class OpenAICompatibleClient(LLMClient):
    """OpenAI 兼容格式客户端（每次请求从 DB 读取配置以支持热更新）"""

    def __init__(self, config):
        """
        Args:
            config: ModelConfig ORM 对象
        """
        from app.utils.crypto import decrypt
        self.config = config
        # 兼容用户填写带后缀的 URL：自动去掉 /embeddings、/chat/completions 后缀
        url = config.api_url.rstrip("/")
        for suffix in ("/embeddings", "/chat/completions"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        self.api_url = url
        self.model_name = config.model_name
        self.api_key = decrypt(config.api_key) if config.api_key else ""
        self.type = config.type
        # 最近一次 chat_stream 的 usage 信息（供调用方在流结束后读取）
        self.last_usage: dict = {}

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(self, messages: list, **kwargs) -> dict:
        """对话补全

        Returns:
            dict: {content, input_tokens, output_tokens, model}
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        payload.update(kwargs)

        start = time.time()
        async with httpx.AsyncClient(timeout=120.0, verify=_build_ssl_context(), trust_env=False) as client:
            resp = await client.post(
                f"{self.api_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            duration_ms = int((time.time() - start) * 1000)
            if resp.status_code != 200:
                # 记录上游响应详情到日志（便于排查），但不返回给客户端（可能含敏感信息）
                logger.error(
                    f"[LLM.chat] 上游响应非 200: status={resp.status_code} url={self.api_url}/chat/completions "
                    f"model={self.model_name} body={resp.text[:500]}"
                )
                raise APIError(
                    f"LLM 调用失败（HTTP {resp.status_code}），请检查模型配置或稍后重试。",
                    status_code=502,
                )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            # 同步设置 last_usage，供调用方读取（与 chat_stream/embed 行为一致）
            self.last_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": data.get("model", self.model_name),
                "total_tokens": usage.get("total_tokens", 0),
            }
            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": data.get("model", self.model_name),
                "duration_ms": duration_ms,
            }

    async def chat_stream(self, messages: list, **kwargs) -> AsyncGenerator[str, None]:
        """流式对话补全，逐步 yield 文本片段

        流结束后，最后一次的 usage 信息会存到 self.last_usage（供调用方读取 token 数）。
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            # 请求在最后一个 chunk 返回 usage 信息
            "stream_options": {"include_usage": True},
        }
        payload.update(kwargs)
        # 合并 kwargs 可能覆盖 stream_options
        if "stream_options" not in kwargs:
            payload["stream_options"] = {"include_usage": True}

        self.last_usage = {}
        async with httpx.AsyncClient(timeout=120.0, verify=_build_ssl_context(), trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{self.api_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    # 记录上游响应详情到日志（便于排查），但不返回给客户端
                    logger.error(
                        f"[LLM.chat_stream] 上游响应非 200: status={resp.status_code} "
                        f"url={self.api_url}/chat/completions model={self.model_name} "
                        f"body={text.decode()[:500]}"
                    )
                    raise APIError(
                        f"LLM 流式调用失败（HTTP {resp.status_code}），请检查模型配置或稍后重试。",
                        status_code=502,
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line = line[len("data: "):]
                    if line.strip() == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(line)
                        # 收集 usage（最后一个 chunk 通常 choices 为空，但带 usage）
                        usage = chunk.get("usage")
                        if usage:
                            self.last_usage = {
                                "input_tokens": usage.get("prompt_tokens", 0),
                                "output_tokens": usage.get("completion_tokens", 0),
                                "model": chunk.get("model", self.model_name),
                            }
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content", "")
                        if piece:
                            yield piece
                    except Exception:
                        continue

    async def embedding(self, texts: list) -> list:
        """向量化文本列表

        Returns:
            list[list[float]]

        Side effect: 更新 self.last_usage（含 input_tokens, model, prompt_tokens_info）
        """
        if not texts:
            return []
        import time as _time
        _start = _time.time()
        payload = {
            "model": self.model_name,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=120.0, verify=_build_ssl_context(), trust_env=False) as client:
            resp = await client.post(
                f"{self.api_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code != 200:
                # 记录上游响应详情到日志（便于排查），但不返回给客户端
                logger.error(
                    f"[LLM.embedding] 上游响应非 200: status={resp.status_code} "
                    f"url={self.api_url}/embeddings model={self.model_name} "
                    f"body={resp.text[:500]}"
                )
                raise APIError(
                    f"Embedding 调用失败（HTTP {resp.status_code}），请检查模型配置或稍后重试。",
                    status_code=502,
                )
            data = resp.json()
            usage = data.get("usage", {})
            self.last_usage = {
                "input_tokens": usage.get("prompt_tokens", sum(len(str(t)) // 4 for t in texts) or 1),
                "output_tokens": 0,
                "model": data.get("model", self.model_name),
                "duration_ms": int((_time.time() - _start) * 1000),
                "total_tokens": usage.get("total_tokens", 0),
            }
            # 按 index 排序保证顺序
            items = data.get("data", [])
            items_sorted = sorted(items, key=lambda x: x.get("index", 0))
            return [item.get("embedding", []) for item in items_sorted]


class ForecastClient:
    """时序预测客户端（统一封装 Chronos-2 / TimesFM 2.5 等本地推理服务）

    约定推理服务暴露统一 POST /predict 端点：
        请求: {series: list[float], horizon: int, quantiles: list[float]}
        响应: {forecasts: list[float], quantiles: dict[str, list[float]], model: str}
    """

    def __init__(self, config):
        """
        Args:
            config: ModelConfig ORM 对象（type=Forecast）
        """
        from app.utils.crypto import decrypt
        self.config = config
        self.api_url = config.api_url.rstrip("/")
        self.model_name = config.model_name
        self.api_key = decrypt(config.api_key) if config.api_key else ""
        # 最近一次预测的元信息（供调用方读取）
        self.last_usage: dict = {}

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def predict(self, series: list, horizon: int,
                      quantiles: list = None) -> dict:
        """时序预测

        Args:
            series: 历史观测值序列
            horizon: 预测步数
            quantiles: 分位数列表，默认 [0.1, 0.5, 0.9]

        Returns:
            dict: {forecasts, quantiles, model, duration_ms, input_points, output_points}
        """
        if not series:
            raise APIError("预测输入序列为空", status_code=400)
        if horizon <= 0:
            raise APIError("预测步数 horizon 必须 > 0", status_code=400)

        payload = {
            "series": series,
            "horizon": horizon,
            "quantiles": quantiles or [0.1, 0.5, 0.9],
        }
        start = time.time()
        async with httpx.AsyncClient(timeout=180.0, verify=_build_ssl_context(), trust_env=False) as client:
            resp = await client.post(
                f"{self.api_url}/predict",
                headers=self._headers(),
                json=payload,
            )
            duration_ms = int((time.time() - start) * 1000)
            if resp.status_code != 200:
                raise APIError(
                    f"Forecast 调用失败({resp.status_code}): {resp.text[:200]}",
                    status_code=502,
                )
            data = resp.json()
            forecasts = data.get("forecasts", [])
            quantile_result = data.get("quantiles", {})
            model = data.get("model", self.model_name)
            # Forecast 是时序预测，没有 token 概念；用 input_points/output_points 记录点数，
            # 保留 input_tokens/output_tokens 仅向后兼容旧的日志读取代码。
            self.last_usage = {
                "input_tokens": 0,                # Forecast 不消耗 token
                "output_tokens": 0,               # Forecast 不消耗 token
                "input_points": len(series),      # 输入数据点数
                "output_points": len(forecasts),  # 输出数据点数
                "model": model,
                "duration_ms": duration_ms,
            }
            return {
                "forecasts": forecasts,
                "quantiles": quantile_result,
                "model": model,
                "duration_ms": duration_ms,
                "input_points": len(series),
                "output_points": len(forecasts),
            }


class ModelManager:
    """模型管理器：从数据库读取启用的模型配置（带内存缓存）

    缓存策略：
    - 首次 get_active_* 时从 DB 读取并构造客户端，缓存在内存中
    - activate/update/delete 时调用 invalidate_cache() 主动失效
    - 避免每次问答/向量化都新建 DB Session + 解密 API Key
    """
    _cache: dict = {}  # {type: client}
    _cache_config_id: dict = {}  # {type: config_id}（用于判断缓存是否还有效）

    @classmethod
    def invalidate_cache(cls, model_type: str = None):
        """失效缓存

        Args:
            model_type: 指定类型（LLM/Embedding/Forecast）；None 则清空全部
        """
        if model_type:
            cls._cache.pop(model_type, None)
            cls._cache_config_id.pop(model_type, None)
        else:
            cls._cache.clear()
            cls._cache_config_id.clear()
        logger.debug(f"[ModelManager] 缓存已失效 type={model_type or 'all'}")

    @classmethod
    def _get_active_config(cls, db, model_type: str):
        """从 DB 读取指定类型的启用配置，返回 (config, config_id)"""
        from app.models import ModelConfig

        config = (
            db.query(ModelConfig)
            .filter(ModelConfig.type == model_type, ModelConfig.is_active == True)  # noqa: E712
            .first()
        )
        return config

    @classmethod
    def _get_or_create_client(cls, model_type: str, client_factory):
        """获取或创建客户端（带缓存）

        Args:
            model_type: LLM / Embedding / Forecast
            client_factory: callable(config) -> client，根据 config 构造客户端
        """
        from app.database import SessionLocal

        # 命中缓存：检查配置是否仍然启用
        if model_type in cls._cache:
            cached_client = cls._cache[model_type]
            cached_config_id = cls._cache_config_id.get(model_type)
            # 用轻量查询确认配置仍然启用且未变更
            db = SessionLocal()
            try:
                current = cls._get_active_config(db, model_type)
                if current and current.id == cached_config_id:
                    return cached_client
                # 配置已变更或失效，清理
                cls._cache.pop(model_type, None)
                cls._cache_config_id.pop(model_type, None)
                if not current:
                    return None
                config = current
            finally:
                db.close()
        else:
            db = SessionLocal()
            try:
                config = cls._get_active_config(db, model_type)
                if not config:
                    return None
            finally:
                db.close()

        # 创建新客户端
        client = client_factory(config)
        cls._cache[model_type] = client
        cls._cache_config_id[model_type] = config.id
        return client

    @classmethod
    def get_active_llm(cls) -> OpenAICompatibleClient:
        """获取启用的 LLM 客户端"""
        client = cls._get_or_create_client("LLM", lambda c: OpenAICompatibleClient(c))
        if not client:
            raise APIError("未配置启用的LLM模型，请先在模型配置页面配置", status_code=400)
        return client

    @classmethod
    def get_active_embedding(cls) -> LLMClient:
        """获取启用的 Embedding 客户端

        仅从数据库读取用户显式配置的 Embedding 模型；未配置时抛 APIError，
        调用方应捕获并降级（如 RAG 降级为直接对话）。
        """
        client = cls._get_or_create_client("Embedding", lambda c: OpenAICompatibleClient(c))
        if not client:
            raise APIError("未配置启用的 Embedding 模型，请在模型配置页添加", status_code=400)
        return client

    @classmethod
    def get_active_forecast(cls) -> ForecastClient:
        """获取启用的 Forecast 客户端（时序预测模型）

        从数据库读取 type=Forecast 且启用的配置；未配置时抛 APIError，
        调用方应捕获并提示用户在模型配置页添加。
        """
        client = cls._get_or_create_client("Forecast", lambda c: ForecastClient(c))
        if not client:
            raise APIError("未配置启用的 Forecast 时序预测模型，请在模型配置页添加", status_code=400)
        return client

    @classmethod
    def reload_forecast(cls, db):
        """强制重新加载 Forecast 客户端（多模型对比时切换激活模型后调用）"""
        cls.invalidate_cache("Forecast")
        # 预加载新配置到缓存
        config = cls._get_active_config(db, "Forecast")
        if config:
            cls._cache["Forecast"] = ForecastClient(config)
            cls._cache_config_id["Forecast"] = config.id


model_manager = ModelManager()
