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
    """获取或创建 collection（使用余弦距离）"""
    client = _get_client()
    return client.get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def _rebuild_collection(name: str):
    """删除并重建 collection（用于 Embedding 维度变化时）"""
    client = _get_client()
    try:
        client.delete_collection(name=name)
        logger.info(f"[VectorStore] 已删除旧 collection: {name}（维度不匹配，重建中）")
    except Exception as e:
        logger.warning(f"[VectorStore] 删除 collection {name} 失败: {e}")
    return client.get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


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
                logger.warning(
                    f"[VectorStore] 检测到 Embedding 维度不匹配，将重建 collection 并清空所有向量数据: {e}"
                )
                collection = _rebuild_collection(self.KNOWLEDGE_COLLECTION)
                # 同时清空缓存 collection（维度也不匹配）
                try:
                    _rebuild_collection(self.CACHE_COLLECTION)
                except Exception:
                    logger.exception("[VectorStore] 重建缓存 collection 失败")
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
            # 兼容 ChromaDB 不支持 where 删除的情况：按 metadata 条件查询后再删除
            # K-P1-10: 用 where 条件查询而非全量 get()，避免大规模知识库 OOM
            try:
                existing = collection.get(where={"knowledge_id": knowledge_id})
                ids_to_delete = existing.get("ids", [])
                if ids_to_delete:
                    collection.delete(ids=ids_to_delete)
            except Exception:
                # 最终回退：按 ID 前缀逐批查询（限制单批数量，防止全量加载）
                logger.warning(f"[VectorStore.delete] where 条件查询失败，回退到按前缀查询 knowledge_id={knowledge_id}")
                # 使用 limit 分批获取，避免全量加载
                existing = collection.get(limit=10000)
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

    def get_by_knowledge_id(self, knowledge_id: int, limit: int = 1) -> list:
        """按 knowledge_id 获取向量数据（用于 BM25 命中但向量未命中的场景）

        Args:
            knowledge_id: 知识 ID
            limit: 最多返回的 chunk 数

        Returns:
            list of dict: [{id, document, metadata, score}]
        """
        collection = _get_collection(self.KNOWLEDGE_COLLECTION)
        try:
            results = collection.get(
                where={"knowledge_id": knowledge_id},
                limit=limit,
            )
        except Exception:
            logger.exception(f"[VectorStore.get_by_knowledge_id] 查询失败 kid={knowledge_id}")
            return []
        out = []
        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        for i in range(len(ids)):
            out.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "score": 0.0,  # 无向量相似度分数
            })
        return out

    def get_batch_by_knowledge_ids(self, knowledge_ids: list, limit_per_kid: int = 1) -> dict:
        """批量获取多个 knowledge_id 的向量数据（K-5: 避免 N+1 查询）

        Args:
            knowledge_ids: 知识 ID 列表
            limit_per_kid: 每个 knowledge 最多返回的 chunk 数

        Returns:
            dict: {knowledge_id: [{id, document, metadata, score}]}
        """
        if not knowledge_ids:
            return {}
        collection = _get_collection(self.KNOWLEDGE_COLLECTION)
        result_map = {}
        try:
            # ChromaDB 支持 $in 操作符批量查询
            results = collection.get(
                where={"knowledge_id": {"$in": knowledge_ids}},
                limit=limit_per_kid * len(knowledge_ids),
            )
        except Exception:
            # $in 不支持时回退到逐个查询
            logger.warning(f"[VectorStore.get_batch] $in 查询失败，回退到逐个查询")
            for kid in knowledge_ids:
                result_map[kid] = self.get_by_knowledge_id(kid, limit_per_kid)
            return result_map

        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        for i in range(len(ids)):
            meta = metas[i] if i < len(metas) else {}
            kid = int(meta.get("knowledge_id", 0)) if meta.get("knowledge_id") else 0
            if not kid:
                continue
            if kid not in result_map:
                result_map[kid] = []
            if len(result_map[kid]) < limit_per_kid:
                result_map[kid].append({
                    "id": ids[i],
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": meta,
                    "score": 0.0,
                })
        return result_map

    # -------- 答案缓存 collection --------
    def add_to_cache(self, question: str, answer_dict: dict, question_embedding: list):
        """将问答对写入缓存

        Args:
            question: 原问题文本
            answer_dict: 答案字典（包含 answer, sources, skill_id, skill_name 等）
            question_embedding: 问题的向量
        """
        from datetime import datetime
        collection = _get_collection(self.CACHE_COLLECTION)
        cache_id = str(uuid.uuid4())
        collection.add(
            ids=[cache_id],
            documents=[question],
            embeddings=[question_embedding],
            metadatas=[{
                "payload": json.dumps(answer_dict, ensure_ascii=False),
                "created_at": datetime.utcnow().isoformat(),
            }],
        )

    def search_cache(self, query_embedding: list, threshold: float = None) -> Optional[dict]:
        """搜索缓存的答案

        Args:
            query_embedding: 查询向量
            threshold: 相似度阈值（None 时使用全局配置 CACHE_SIMILARITY_THRESHOLD）

        Returns:
            命中缓存时返回 answer_dict，否则 None
        """
        if threshold is None:
            # 延迟导入避免循环依赖，使用全局配置阈值
            from app.config import CACHE_SIMILARITY_THRESHOLD
            threshold = CACHE_SIMILARITY_THRESHOLD
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

        # TTL 检查：超过过期时间的缓存视为未命中
        from app.config import CACHE_TTL_SECONDS
        from datetime import datetime, timedelta
        created_at_str = meta.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                if datetime.utcnow() - created_at > timedelta(seconds=CACHE_TTL_SECONDS):
                    logger.info(f"[search_cache] 缓存已过期（created_at={created_at_str}），跳过")
                    return None
            except (ValueError, TypeError):
                # created_at 格式异常时忽略 TTL 检查（兼容旧数据）
                pass

        payload = meta.get("payload", "{}")
        try:
            return json.loads(payload)
        except Exception:
            return None

    def clear_cache(self) -> int:
        """清空答案缓存 collection（知识更新/删除时调用，防止返回过期内容）

        Returns:
            被清除的缓存条数（无法精确统计时返回 0）
        """
        try:
            client = _get_client()
            client.delete_collection(name=self.CACHE_COLLECTION)
            # 立即重建空 collection，避免后续写入报错
            _get_collection(self.CACHE_COLLECTION)
            logger.info("[VectorStore] 答案缓存 collection 已清空")
            return 0
        except Exception:
            logger.exception("[VectorStore] 清空答案缓存失败")
            return 0


# 单例
vector_store = VectorStore()
