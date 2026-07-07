"""Embedding 服务"""
import logging
from typing import Optional

from app.services.llm_client import model_manager, ModelManager

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务，依赖 ModelManager 获取启用的 Embedding 客户端

    每次调用都会记录 TokenUsage 日志（call_type=embedding）。
    """

    async def embed(self, texts: list, source: str = "internal") -> list:
        """批量向量化文本

        Args:
            texts: 文本列表
            source: 调用来源（embedding/sync_index/search/qa）

        Returns:
            list[list[float]]
        """
        if not texts:
            return []
        client = model_manager.get_active_embedding()
        # 分批处理避免单次请求过大
        batch_size = 32
        all_vecs = []
        total_input_tokens = 0
        total_duration_ms = 0
        model_name = getattr(client, "model_name", "embedding")
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            vecs = await client.embedding(batch)
            all_vecs.extend(vecs)
            usage = getattr(client, "last_usage", {}) or {}
            total_input_tokens += usage.get("input_tokens", 0)
            total_duration_ms += usage.get("duration_ms", 0)
            model_name = usage.get("model", model_name)
        # 记录调用日志
        try:
            self._log_usage(
                source=source,
                model_name=model_name,
                input_tokens=total_input_tokens,
                duration_ms=total_duration_ms,
                text_count=len(texts),
            )
        except Exception as e:
            logger.warning(f"[embedding_service] 记录调用日志失败: {e}")
        return all_vecs

    def _log_usage(self, source: str, model_name: str, input_tokens: int,
                   duration_ms: int, text_count: int):
        """写入 TokenUsage 记录"""
        from app.database import SessionLocal
        from app.models import TokenUsage
        db = SessionLocal()
        try:
            usage = TokenUsage(
                call_type="embedding",
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=0,
                duration_ms=duration_ms,
                source=source,
            )
            db.add(usage)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


embedding_service = EmbeddingService()
