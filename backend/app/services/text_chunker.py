"""文本分块器：按段落 + 长度进行分块"""


def chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """将长文本切分为多个片段

    策略：先按段落（空行）切分，再对超长段落按 chunk_size 切分，
    最终尽量保证每个 chunk 不超过 chunk_size，相邻 chunk 有 overlap 重叠。
    """
    if not text or not text.strip():
        return []

    # 按段落切分（保留换行结构）
    paragraphs = text.split("\n")
    chunks = []
    current = ""

    for para in paragraphs:
        # 单段过长则硬切
        if len(para) > chunk_size:
            # 先把当前累积的内容放入
            if current.strip():
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(para), chunk_size - overlap):
                piece = para[i:i + chunk_size]
                if piece:
                    chunks.append(piece.strip())
            continue

        # 累积到 chunk_size
        if len(current) + len(para) + 1 > chunk_size:
            if current.strip():
                chunks.append(current.strip())
                # 保留 overlap 文本作为下一段开头
                if overlap > 0 and len(current) > overlap:
                    current = current[-overlap:] + "\n" + para
                else:
                    current = para
            else:
                current = para
        else:
            current = current + "\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c]
