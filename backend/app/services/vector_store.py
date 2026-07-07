"""ChromaDB 向量存储服务"""
import json
import logging
import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings

from app.config import VECTOR_DB_PATH

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """获取/初始化 ChromaDB 持久化客户端（单例）"""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    return _client


def _get_collection(name: str):
    """获取或创建 collection"""
    client = _get_client()
    return client.get_or_create_collection(name=name)


def _rebuild_collection(name: str):
    """删除并重建 collection（用于 Embedding 维度变化时）"""
    client = _get_client()
    try:
        client.delete_collection(name=name)
        logger.info(f"[VectorStore] 已删除旧 collection: {name}（维度不匹配，重建中）")
    except Exception as e:
        logger.warning(f"[VectorStore] 删除 collection {name} 失败: {e}")
    return client.get_or_create_collection(name=name)


class VectorStore:
    """向量存储封装"""

    KNOWLEDGE_COLLECTION = "knowledge"
    CACHE_COLLECTION = "answer_cache"

    # -------- 知识库 collection --------
    def add(self, knowledge_id: int, chunks: list, embeddings: list, metadata: list):
        """添加向量数据

        Args:
            knowledge_id: 知识ID
            chunks: 文本片段列表
            embeddings: 对应的向量列表
            metadata: 每个片段的 metadata（含 title, category_id, chunk_index）
        """
        if not chunks:
            return
        collection = _get_collection(self.KNOWLEDGE_COLLECTION)
        ids = [f"{knowledge_id}_{i}" for i in range(len(chunks))]
        # metadata 中的值必须是基础类型
        safe_meta = []
        for m in metadata:
            item = {}
            for k, v in m.items():
                if v is None:
                    item[k] = ""
                elif isinstance(v, (int, float, bool, str)):
                    item[k] = v
                else:
                    item[k] = str(v)
            safe_meta.append(item)
        try:
            collection.add(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=safe_meta,
            )
        except Exception as e:
            # 维度不匹配时自动重建 collection 后重试
            if "embedding with dimension" in str(e) or "dimension" in str(e).lower():
                logger.warning(f"[VectorStore] 检测到维度不匹配，重建 collection: {e}")
                collection = _rebuild_collection(self.KNOWLEDGE_COLLECTION)
                # 同时清空缓存 collection（维度也不匹配）
                try:
                    _rebuild_collection(self.CACHE_COLLECTION)
                except Exception:
                    pass
                collection.add(
                    ids=ids,
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=safe_meta,
                )
            else:
                raise

    def delete(self, knowledge_id: int):
        """删除某 knowledge 的所有向量"""
        collection = _get_collection(self.KNOWLEDGE_COLLECTION)
        # 按 metadata 过滤删除
        try:
            collection.delete(where={"knowledge_id": knowledge_id})
        except Exception:
            # 兼容 ChromaDB 不支持 where 删除的情况：按 ID 前缀删除
            existing = collection.get()
            ids_to_delete = [i for i in existing.get("ids", []) if i.startswith(f"{knowledge_id}_")]
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)

    def search(self, query_embedding: list, where: Optional[dict] = None,
               top_k: int = 5, collection_name: str = None) -> list:
        """向量检索

        Returns:
            list of dict: [{id, document, metadata, distance}]
        """
        coll_name = collection_name or self.KNOWLEDGE_COLLECTION
        collection = _get_collection(coll_name)
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where
        results = collection.query(**kwargs)
        out = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for i in range(len(ids)):
            distance = dists[i] if i < len(dists) else 0.0
            # 距离转相似度（假设为余弦距离）
            score = 1.0 - distance if distance <= 1.0 else 0.0
            out.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": distance,
                "score": score,
            })
        return out

    # -------- 答案缓存 collection --------
    def add_to_cache(self, question: str, answer_dict: dict, question_embedding: list):
        """将问答对写入缓存

        Args:
            question: 原问题文本
            answer_dict: 答案字典（包含 answer, sources, skill_id, skill_name 等）
            question_embedding: 问题的向量
        """
        collection = _get_collection(self.CACHE_COLLECTION)
        cache_id = str(uuid.uuid4())
        collection.add(
            ids=[cache_id],
            documents=[question],
            embeddings=[question_embedding],
            metadatas=[{"payload": json.dumps(answer_dict, ensure_ascii=False)}],
        )

    def search_cache(self, query_embedding: list, threshold: float = 0.95) -> Optional[dict]:
        """搜索缓存的答案

        Args:
            query_embedding: 查询向量
            threshold: 相似度阈值

        Returns:
            命中缓存时返回 answer_dict，否则 None
        """
        collection = _get_collection(self.CACHE_COLLECTION)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
        )
        ids = results.get("ids", [[]])[0]
        if not ids:
            return None
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        distance = dists[0] if dists else 1.0
        score = 1.0 - distance if distance <= 1.0 else 0.0
        if score < threshold:
            return None
        meta = metas[0] if metas else {}
        payload = meta.get("payload", "{}")
        try:
            return json.loads(payload)
        except Exception:
            return None


# 单例
vector_store = VectorStore()
