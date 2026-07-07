"""问答缓存服务"""
from typing import Optional

from app.config import CACHE_SIMILARITY_THRESHOLD
from app.services.vector_store import vector_store


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
            return None

    def put(self, question: str, answer: dict, question_embedding: list):
        """存入缓存"""
        try:
            vector_store.add_to_cache(question=question, answer_dict=answer, question_embedding=question_embedding)
        except Exception:
            # 缓存写入失败不影响主流程
            pass


answer_cache = AnswerCache()
