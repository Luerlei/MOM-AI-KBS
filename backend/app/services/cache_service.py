"""问答缓存服务"""
import logging
from typing import Optional

from app.config import CACHE_SIMILARITY_THRESHOLD
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


class AnswerCache:
    """问答答案缓存，基于 ChromaDB answer_cache collection"""

    def get(self, question_embedding: list) -> Optional[dict]:
        """搜索缓存，命中返回 answer_dict，否则 None"""
        try:
            return vector_store.search_cache(
                query_embedding=question_embedding,
                threshold=CACHE_SIMILARITY_THRESHOLD,
            )
        except Exception:
            logger.exception("[AnswerCache] 读取缓存失败")
            return None

    def put(self, question: str, answer: dict, question_embedding: list):
        """存入缓存"""
        try:
            vector_store.add_to_cache(question=question, answer_dict=answer, question_embedding=question_embedding)
        except Exception:
            # 缓存写入失败不影响主流程，但记录日志便于排查
            logger.exception(f"[AnswerCache] 写入缓存失败 question={question[:50]}")

    def clear(self):
        """清空答案缓存（知识更新/删除时调用，防止返回过期内容）"""
        try:
            vector_store.clear_cache()
        except Exception:
            logger.exception("[AnswerCache] 清空缓存失败")


answer_cache = AnswerCache()
