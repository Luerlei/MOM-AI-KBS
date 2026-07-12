"""Prompt 组装器"""
import logging

logger = logging.getLogger(__name__)

# 粗略 token 估算：中文按 1.5 字/token，英文按 4 字符/token
# 这里用简单近似：1 token ≈ 2 个字符（混合中英文的经验值）
_CHARS_PER_TOKEN = 2.0

# 默认上下文 token 上限（留出空间给 system prompt + question + 输出）
MAX_CONTEXT_TOKENS = 4000


def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数"""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def assemble(skill, question: str, context_chunks: list) -> list:
    """组装 LLM messages

    Args:
        skill: Skill ORM 对象
        question: 用户问题
        context_chunks: 检索到的知识片段列表 [{document, metadata, score}]

    Returns:
        list[dict]: [{"role":"system","content":prompt}, {"role":"user","content":question}]
    """
    # 组装上下文文本，带长度控制
    context_text = ""
    if context_chunks:
        parts = []
        used_tokens = 0
        truncated = 0
        for i, c in enumerate(context_chunks, 1):
            doc = c.get("document", "") if isinstance(c, dict) else getattr(c, "document", "")
            meta = c.get("metadata", {}) if isinstance(c, dict) else getattr(c, "metadata", {})
            title = meta.get("title", "未知来源") if isinstance(meta, dict) else "未知来源"
            piece = f"[{i}] 来源：{title}\n{doc}"
            piece_tokens = _estimate_tokens(piece)
            # 检查加上该片段后是否超出上限
            if used_tokens + piece_tokens > MAX_CONTEXT_TOKENS:
                # 部分截取剩余空间
                remaining_chars = int((MAX_CONTEXT_TOKENS - used_tokens) * _CHARS_PER_TOKEN)
                if remaining_chars > 100:
                    piece = piece[:remaining_chars] + "..."
                    parts.append(piece)
                    used_tokens = MAX_CONTEXT_TOKENS
                truncated = len(context_chunks) - i + 1
                break
            parts.append(piece)
            used_tokens += piece_tokens
        context_text = "\n\n".join(parts)
        if truncated > 0:
            logger.info(
                f"[prompt_assembler] 上下文过长，已截断最后 {truncated} 个片段 "
                f"(token≈{used_tokens}/{MAX_CONTEXT_TOKENS})"
            )

    # 使用 Skill 的 prompt_template
    template = skill.prompt_template or (
        "你是MOM系统AI知识库助手。请根据以下知识上下文回答用户问题。\n\n"
        "知识上下文：\n{context}\n\n"
        "回答要求：\n"
        "1. 请基于上述上下文回答，若上下文不足请如实说明\n"
        "2. 在引用某个知识片段时，请在相应内容末尾标注来源编号，如 [1]、[2]\n"
        "3. 回答应准确、简洁、条理清晰"
    )

    # 替换变量
    prompt = template.replace("{context}", context_text).replace("{question}", question)

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]
