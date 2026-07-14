"""BM25 检索服务（Okapi BM25 算法实现）

替换原有 SQLite LIKE 简单打分，实现真正的 BM25 算法：
score(D, Q) = Σ IDF(qi) × (f(qi, D) × (k1 + 1)) / (f(qi, D) + k1 × (1 - b + b × |D| / avgdl))

特点：
- 纯 Python 实现，零外部依赖
- 内存索引 + 增量更新（知识增删改时同步）
- 中文分词（jieba）+ 英文分词（空格）
- 文档长度归一化 + IDF 加权
- 按需构建：首次查询时从数据库加载 published 知识构建索引
"""
import logging
import math
import re
import threading
import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# BM25 参数（标准 Okapi 参数）
K1 = 1.5  # 词频饱和参数
B = 0.75  # 文档长度归一化参数

# 标点符号正则
_PUNCT_RE = re.compile(r'^[\s,，。.!！?？;；、:：()（）\[\]【】""\'\"·\-—…]+$')


def _tokenize(text: str) -> List[str]:
    """分词：jieba 中文 + 空格英文，过滤单字符和标点"""
    if not text or not text.strip():
        return []

    try:
        import jieba
        raw_tokens = list(jieba.cut(text))
    except ImportError:
        raw_tokens = re.split(r'[\s,，。.!！?？;；、:：]+', text)
    except Exception:
        raw_tokens = re.split(r'[\s,，。.!！?？;；、:：]+', text)

    tokens = []
    for t in raw_tokens:
        t = t.strip().lower()
        if not t or len(t) < 1:
            continue
        if _PUNCT_RE.match(t):
            continue
        tokens.append(t)
    return tokens


class BM25Index:
    """Okapi BM25 内存索引（线程安全）

    索引结构：
    - inverted_index: {token: {doc_id: term_frequency}}
    - doc_lengths: {doc_id: document_length}
    - doc_freq: {token: number_of_docs_containing_token}
    - avgdl: 平均文档长度
    - num_docs: 文档总数
    """

    def __init__(self, k1: float = K1, b: float = B):
        self.k1 = k1
        self.b = b
        self.inverted_index: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.doc_lengths: Dict[int, int] = {}
        self.doc_titles: Dict[int, str] = {}  # 用于调试
        self.doc_freq: Dict[str, int] = defaultdict(int)
        self.num_docs: int = 0
        self.avgdl: float = 0.0
        self._lock = threading.RLock()
        self._built = False
        self._built_at: float = 0.0
        self._doc_ids: set = set()

    def add_document(self, doc_id: int, title: str, content: str):
        """添加或更新单个文档（增量更新）"""
        with self._lock:
            # 若已存在先移除
            if doc_id in self._doc_ids:
                self._remove_document(doc_id)

            # 合并标题和内容作为文档文本（标题权重通过重复实现）
            # 标题中的词出现 2 次（权重 ×2，与原 LIKE 打分逻辑一致）
            title_tokens = _tokenize(title)
            content_tokens = _tokenize(content)
            all_tokens = title_tokens + title_tokens + content_tokens

            tf = Counter(all_tokens)
            doc_len = len(all_tokens)

            for token, freq in tf.items():
                self.inverted_index[token][doc_id] = freq
                self.doc_freq[token] += 1

            self.doc_lengths[doc_id] = doc_len
            self.doc_titles[doc_id] = title
            self._doc_ids.add(doc_id)
            self.num_docs = len(self._doc_ids)
            total_len = sum(self.doc_lengths.values())
            self.avgdl = total_len / self.num_docs if self.num_docs > 0 else 0.0

    def _remove_document(self, doc_id: int):
        """移除单个文档"""
        if doc_id not in self._doc_ids:
            return
        # 从倒排索引中移除
        tokens_to_clean = []
        for token, postings in self.inverted_index.items():
            if doc_id in postings:
                del postings[doc_id]
                self.doc_freq[token] -= 1
                if self.doc_freq[token] <= 0:
                    tokens_to_clean.append(token)
        for token in tokens_to_clean:
            self.inverted_index.pop(token, None)
            self.doc_freq.pop(token, None)
        # 从文档长度记录中移除
        self.doc_lengths.pop(doc_id, None)
        self.doc_titles.pop(doc_id, None)
        self._doc_ids.discard(doc_id)
        self.num_docs = len(self._doc_ids)
        total_len = sum(self.doc_lengths.values())
        self.avgdl = total_len / self.num_docs if self.num_docs > 0 else 0.0

    def remove_document(self, doc_id: int):
        """移除单个文档（线程安全）"""
        with self._lock:
            self._remove_document(doc_id)

    def clear(self):
        """清空索引"""
        with self._lock:
            self.inverted_index.clear()
            self.doc_lengths.clear()
            self.doc_titles.clear()
            self.doc_freq.clear()
            self.num_docs = 0
            self.avgdl = 0.0
            self._doc_ids.clear()
            self._built = False

    def search(self, query: str, top_k: int = 10,
               allowed_doc_ids: Optional[set] = None) -> List[Tuple[int, float]]:
        """BM25 检索

        Args:
            query: 查询文本
            top_k: 最多返回的文档数
            allowed_doc_ids: 限定搜索范围（如 scope 过滤后的 knowledge_id 集合），None 表示全部

        Returns:
            list of (doc_id, bm25_score) 按分数降序
        """
        with self._lock:
            if self.num_docs == 0:
                return []

            query_tokens = _tokenize(query)
            if not query_tokens:
                return []

            scores: Dict[int, float] = defaultdict(float)
            for token in query_tokens:
                postings = self.inverted_index.get(token)
                if not postings:
                    continue
                # IDF = ln(1 + (N - n + 0.5) / (n + 0.5))，N 为文档总数，n 为包含该词的文档数
                n = self.doc_freq.get(token, 0)
                idf = math.log(1 + (self.num_docs - n + 0.5) / (n + 0.5))
                if idf <= 0:
                    continue
                for doc_id, tf in postings.items():
                    if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
                        continue
                    doc_len = self.doc_lengths.get(doc_id, 0)
                    # BM25 打分
                    norm = 1 - self.b + self.b * (doc_len / self.avgdl if self.avgdl > 0 else 0)
                    score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
                    scores[doc_id] += score

            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            return ranked[:top_k]

    def stats(self) -> dict:
        """索引统计信息"""
        with self._lock:
            return {
                "num_docs": self.num_docs,
                "num_tokens": len(self.inverted_index),
                "avgdl": round(self.avgdl, 2),
                "built": self._built,
                "built_at": self._built_at,
            }


# 全局单例
bm25_index = BM25Index()


def rebuild_bm25_index(db):
    """从数据库全量重建 BM25 索引

    仅索引 status=published 的知识
    """
    from app.models import Knowledge
    start = time.time()
    bm25_index.clear()
    try:
        items = db.query(Knowledge).filter(Knowledge.status == "published").all()
        for k in items:
            bm25_index.add_document(k.id, k.title or "", k.content or "")
        bm25_index._built = True
        bm25_index._built_at = time.time()
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"[bm25] 全量重建完成 docs={bm25_index.num_docs} tokens={len(bm25_index.inverted_index)} elapsed={elapsed}ms")
    except Exception:
        logger.exception("[bm25] 全量重建失败")
        bm25_index._built = False


def ensure_bm25_index(db):
    """按需构建索引（首次查询时触发）"""
    if not bm25_index._built:
        rebuild_bm25_index(db)
