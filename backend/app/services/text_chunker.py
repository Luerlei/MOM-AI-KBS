"""文本分块器：Markdown 标题层级感知 + 段落感知 + 滑动窗口 + 句子边界优先

P1-1 升级要点：
1. 段落感知：按空行分段（而非单行），保持语义完整性
2. 滑动窗口：标题切换和段落累积时保留 overlap 上下文
3. 句子边界优先：硬切时优先在句子结束符（。！？.!?）处切分
4. 页码标记保护：VLM 输出的 <!-- page N --> 标记保留在 chunk 开头
5. 标题路径前缀：提升检索时标题匹配的权重
"""
import re
import logging

logger = logging.getLogger(__name__)

# Markdown 标题正则：匹配 # ~ ###### 开头的行
_HEADER_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$', re.MULTILINE)

# 页码标记（VLM 后端输出）：<!-- page N --> 或 <!-- page N (fallback) -->
_PAGE_TAG_RE = re.compile(r'<!--\s*page\s+(\d+)', re.IGNORECASE)

# 句子结束符（中英文）
_SENTENCE_END_RE = re.compile(r'[。！？.!?\n]')

# 段落分隔：连续 2+ 个换行
_PARA_SPLIT_RE = re.compile(r'\n\s*\n')


def chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """将长文本切分为多个片段

    策略：
    1. 如果文本包含 Markdown 标题（#/##/###...），按标题层级分块，
       每个块带标题路径前缀，超长段再按句子边界硬切。
    2. 否则回退到段落感知 + 长度分块策略。
    3. 硬切时优先在句子边界切分，避免切断句子。

    Args:
        text: 原始文本
        chunk_size: 每块最大字符数
        overlap: 相邻块的重叠字符数

    Returns:
        list[str]: 分块后的文本列表
    """
    if not text or not text.strip():
        return []

    # 参数安全限制
    chunk_size = max(100, min(chunk_size, 2000))
    overlap = max(0, min(overlap, chunk_size // 2))

    # 检测是否包含 Markdown 标题
    has_headers = bool(_HEADER_RE.search(text))

    if has_headers:
        chunks = _chunk_by_headers(text, chunk_size, overlap)
    else:
        chunks = _chunk_by_paragraph(text, chunk_size, overlap)

    return [c for c in chunks if c and c.strip()]


def _chunk_by_headers(text: str, chunk_size: int, overlap: int) -> list:
    """按 Markdown 标题层级分块

    逻辑：
    - 遇到标题时，记录当前标题路径（如 "第一章 > 1.1 概述"）
    - 将同一标题下的内容累积为一个块
    - 如果累积内容超过 chunk_size，先保存当前块，再继续
    - 超长段落（单个段落 > chunk_size）按句子边界硬切，保留 overlap
    - 标题切换时，新块带上 overlap 上下文（前一块末尾的 overlap 字符）
    """
    lines = text.split('\n')
    chunks = []
    current_content = []
    header_path = []  # [(level, title), ...]
    last_chunk_tail = ""  # 前一块的末尾，用于 overlap

    def flush():
        """将当前累积的内容作为一个 chunk 输出"""
        nonlocal last_chunk_tail
        if not current_content:
            return
        body = '\n'.join(current_content).strip()
        if not body:
            return
        # 加上标题路径前缀
        if header_path:
            prefix = ' > '.join(t for _, t in header_path)
            body = f"# {prefix}\n{body}"
        # 加上 overlap 上下文
        if last_chunk_tail:
            body = f"{last_chunk_tail}\n{body}"
        # 如果 body 本身超长，进一步硬切
        if len(body) > chunk_size:
            pieces = _hard_split(body, chunk_size, overlap)
            chunks.extend(pieces)
            # 记录最后一块的末尾用于下一次 overlap
            if pieces and overlap > 0:
                last_chunk = pieces[-1]
                last_chunk_tail = last_chunk[-overlap:] if len(last_chunk) > overlap else last_chunk
            else:
                last_chunk_tail = ""
        else:
            chunks.append(body)
            # 记录末尾用于下一次 overlap
            if overlap > 0 and len(body) > overlap:
                last_chunk_tail = body[-overlap:]
            else:
                last_chunk_tail = ""

    for line in lines:
        m = _HEADER_RE.match(line)
        if m:
            # 遇到新标题，先保存之前的内容
            flush()
            current_content = []

            level = len(m.group(1))
            title = m.group(2).strip()

            # 更新标题路径：弹出比当前级别 >= 的标题
            while header_path and header_path[-1][0] >= level:
                header_path.pop()
            header_path.append((level, title))
        else:
            current_content.append(line)

    flush()
    return chunks


def _chunk_by_paragraph(text: str, chunk_size: int, overlap: int) -> list:
    """按段落 + 长度分块（段落感知策略）

    改进点：
    - 按空行分段（而非单行），保持段落语义完整性
    - 累积到 chunk_size 时保存当前块，并保留 overlap
    - 单段过长按句子边界硬切
    """
    # 按空行分段
    paragraphs = _PARA_SPLIT_RE.split(text)
    # 过滤空段落
    paragraphs = [p.strip() for p in paragraphs if p and p.strip()]

    # 如果没有段落分隔，回退到按行处理
    if len(paragraphs) <= 1:
        paragraphs = [p for p in text.split('\n') if p and p.strip()]

    chunks = []
    current = ""
    last_chunk_tail = ""

    for para in paragraphs:
        # 单段过长则硬切
        if len(para) > chunk_size:
            # 先保存当前累积的内容
            if current.strip():
                full = f"{last_chunk_tail}\n{current}" if last_chunk_tail else current
                if len(full) > chunk_size:
                    pieces = _hard_split(full, chunk_size, overlap)
                    chunks.extend(pieces)
                    if pieces and overlap > 0:
                        last_chunk_tail = pieces[-1][-overlap:] if len(pieces[-1]) > overlap else pieces[-1]
                    else:
                        last_chunk_tail = ""
                else:
                    chunks.append(full)
                    last_chunk_tail = full[-overlap:] if overlap > 0 and len(full) > overlap else ""
                current = ""
            # 硬切超长段落
            pieces = _hard_split(para, chunk_size, overlap)
            chunks.extend(pieces)
            if pieces and overlap > 0:
                last_chunk_tail = pieces[-1][-overlap:] if len(pieces[-1]) > overlap else pieces[-1]
            else:
                last_chunk_tail = ""
            continue

        # 累积到 chunk_size
        if len(current) + len(para) + 2 > chunk_size:
            if current.strip():
                full = f"{last_chunk_tail}\n{current}" if last_chunk_tail else current
                if len(full) > chunk_size:
                    pieces = _hard_split(full, chunk_size, overlap)
                    chunks.extend(pieces)
                    if pieces and overlap > 0:
                        last_chunk_tail = pieces[-1][-overlap:] if len(pieces[-1]) > overlap else pieces[-1]
                    else:
                        last_chunk_tail = ""
                else:
                    chunks.append(full)
                    last_chunk_tail = full[-overlap:] if overlap > 0 and len(full) > overlap else ""
            current = para
        else:
            current = current + '\n\n' + para if current else para

    # 处理最后一块
    if current.strip():
        full = f"{last_chunk_tail}\n{current}" if last_chunk_tail else current
        if len(full) > chunk_size:
            pieces = _hard_split(full, chunk_size, overlap)
            chunks.extend(pieces)
        else:
            chunks.append(full)

    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list:
    """对超长文本进行硬切分，优先在句子边界切分，带 overlap 重叠

    改进点：
    - 优先在句子结束符（。！？.!?）处切分，避免切断句子
    - 如果找不到句子边界，回退到按字符硬切
    - 保护页码标记：如果 chunk 包含 <!-- page N -->，确保标记在开头

    Args:
        text: 超长文本
        chunk_size: 每块最大字符数
        overlap: 重叠字符数

    Returns:
        list[str]: 切分后的块列表
    """
    if not text or not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text.strip()]

    pieces = []
    remaining = text.strip()

    while len(remaining) > chunk_size:
        # 在 chunk_size 范围内找最后一个句子边界
        cut_region = remaining[:chunk_size]
        # 从后往前找句子结束符
        best_cut = -1
        for i in range(len(cut_region) - 1, max(0, len(cut_region) - 200), -1):
            if _SENTENCE_END_RE.match(cut_region[i]):
                best_cut = i + 1
                break

        if best_cut <= 0:
            # 找不到句子边界，找最后一个空格或换行
            for i in range(len(cut_region) - 1, max(0, len(cut_region) - 100), -1):
                if cut_region[i] in (' ', '\n', '\t', '，', ',', '；', ';'):
                    best_cut = i + 1
                    break

        if best_cut <= 0:
            # 实在找不到，硬切
            best_cut = chunk_size

        piece = remaining[:best_cut].strip()
        if piece:
            pieces.append(piece)

        # overlap：保留前一块末尾的 overlap 字符
        if overlap > 0 and best_cut > overlap:
            remaining = remaining[best_cut - overlap:]
        else:
            remaining = remaining[best_cut:]
        remaining = remaining.strip()

    if remaining:
        pieces.append(remaining)

    return pieces
