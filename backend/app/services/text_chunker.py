"""文本分块器：支持 Markdown 标题层级感知分块 + 通用段落分块"""
import re
import logging

logger = logging.getLogger(__name__)

# Markdown 标题正则：匹配 # ~ ###### 开头的行（re.MULTILINE 使 ^ 匹配每行开头）
_HEADER_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$', re.MULTILINE)


def chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """将长文本切分为多个片段

    策略：
    1. 如果文本包含 Markdown 标题（#/##/###...），按标题层级分块，
       每个块带标题路径前缀，超长段再按 chunk_size 硬切。
    2. 否则回退到段落 + 长度分块策略。

    Args:
        text: 原始文本
        chunk_size: 每块最大字符数
        overlap: 相邻块的重叠字符数

    Returns:
        list[str]: 分块后的文本列表
    """
    if not text or not text.strip():
        return []

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
    - 超长段落（单个段落 > chunk_size）按 chunk_size 硬切，保留 overlap
    """
    lines = text.split('\n')
    chunks = []
    current_content = []
    header_path = []  # [(level, title), ...]

    def flush():
        """将当前累积的内容作为一个 chunk 输出"""
        if not current_content:
            return
        body = '\n'.join(current_content).strip()
        if not body:
            return
        # 加上标题路径前缀
        if header_path:
            prefix = ' > '.join(t for _, t in header_path)
            body = f"# {prefix}\n{body}"
        # 如果 body 本身超长，进一步硬切
        if len(body) > chunk_size:
            chunks.extend(_hard_split(body, chunk_size, overlap))
        else:
            chunks.append(body)

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
    """按段落 + 长度分块（原始策略）"""
    paragraphs = text.split('\n')
    chunks = []
    current = ""

    for para in paragraphs:
        # 单段过长则硬切
        if len(para) > chunk_size:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split(para, chunk_size, overlap))
            continue

        # 累积到 chunk_size
        if len(current) + len(para) + 1 > chunk_size:
            if current.strip():
                chunks.append(current.strip())
                if overlap > 0 and len(current) > overlap:
                    current = current[-overlap:] + '\n' + para
                else:
                    current = para
            else:
                current = para
        else:
            current = current + '\n' + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list:
    """对超长文本进行硬切分，带 overlap 重叠

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
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        piece = text[i:i + chunk_size]
        if piece.strip():
            pieces.append(piece.strip())
        if i + chunk_size >= len(text):
            break
    return pieces
