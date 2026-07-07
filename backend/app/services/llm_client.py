"""LLM 客户端抽象层（OpenAI 兼容格式）"""
import ssl
import time
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator

import httpx

from app.utils.response import APIError


def _build_ssl_context() -> ssl.SSLContext:
    """构建兼容性更好的 SSL 上下文（降低安全级别以兼容部分服务商）"""
    ctx = ssl.create_default_context()
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
                raise APIError(
                    f"LLM 调用失败({resp.status_code}): {resp.text[:200]}",
                    status_code=502,
                )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {
                "content": content,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
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
                    raise APIError(
                        f"LLM 流式调用失败({resp.status_code}): {text.decode()[:200]}",
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
                raise APIError(
                    f"Embedding 调用失败({resp.status_code}): {resp.text[:200]}",
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
            self.last_usage = {
                "input_tokens": len(series),    # 复用 token 字段记录输入点数
                "output_tokens": len(forecasts),  # 复用 token 字段记录输出点数
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
    """模型管理器：从数据库读取启用的模型配置"""

    @staticmethod
    def get_active_llm() -> OpenAICompatibleClient:
        """获取启用的 LLM 客户端"""
        from app.database import SessionLocal
        from app.models import ModelConfig

        db = SessionLocal()
        try:
            config = (
                db.query(ModelConfig)
                .filter(ModelConfig.type == "LLM", ModelConfig.is_active == True)  # noqa: E712
                .first()
            )
            if not config:
                raise APIError("未配置启用的LLM模型，请先在模型配置页面配置", status_code=400)
            return OpenAICompatibleClient(config)
        finally:
            db.close()

    @staticmethod
    def get_active_embedding() -> LLMClient:
        """获取启用的 Embedding 客户端

        仅从数据库读取用户显式配置的 Embedding 模型；未配置时抛 APIError，
        调用方应捕获并降级（如 RAG 降级为直接对话）。
        """
        from app.database import SessionLocal
        from app.models import ModelConfig

        db = SessionLocal()
        try:
            config = (
                db.query(ModelConfig)
                .filter(ModelConfig.type == "Embedding", ModelConfig.is_active == True)  # noqa: E712
                .first()
            )
            if config:
                return OpenAICompatibleClient(config)
        finally:
            db.close()

        # 未配置外部 Embedding 模型时抛错，调用方应捕获并降级（如 RAG 降级为直接对话）
        raise APIError("未配置启用的 Embedding 模型，请在模型配置页添加", status_code=400)

    @staticmethod
    def get_active_forecast() -> ForecastClient:
        """获取启用的 Forecast 客户端（时序预测模型）

        从数据库读取 type=Forecast 且启用的配置；未配置时抛 APIError，
        调用方应捕获并提示用户在模型配置页添加。
        """
        from app.database import SessionLocal
        from app.models import ModelConfig

        db = SessionLocal()
        try:
            config = (
                db.query(ModelConfig)
                .filter(ModelConfig.type == "Forecast", ModelConfig.is_active == True)  # noqa: E712
                .first()
            )
            if config:
                return ForecastClient(config)
        finally:
            db.close()

        raise APIError("未配置启用的 Forecast 时序预测模型，请在模型配置页添加", status_code=400)


model_manager = ModelManager()
