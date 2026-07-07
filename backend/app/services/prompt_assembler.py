"""Prompt 组装器"""


def assemble(skill, question: str, context_chunks: list) -> list:
    """组装 LLM messages

    Args:
        skill: Skill ORM 对象
        question: 用户问题
        context_chunks: 检索到的知识片段列表 [{document, metadata, score}]

    Returns:
        list[dict]: [{"role":"system","content":prompt}, {"role":"user","content":question}]
    """
    # 组装上下文文本
    context_text = ""
    if context_chunks:
        parts = []
        for i, c in enumerate(context_chunks, 1):
            doc = c.get("document", "") if isinstance(c, dict) else getattr(c, "document", "")
            meta = c.get("metadata", {}) if isinstance(c, dict) else getattr(c, "metadata", {})
            title = meta.get("title", "未知来源") if isinstance(meta, dict) else "未知来源"
            parts.append(f"[{i}] 来源：{title}\n{doc}")
        context_text = "\n\n".join(parts)

    # 使用 Skill 的 prompt_template
    template = skill.prompt_template or "你是MOM系统AI知识库助手。请根据以下知识上下文回答用户问题。\n\n知识上下文：\n{context}\n\n请基于上述上下文回答，若上下文不足请如实说明。"

    # 替换变量
    prompt = template.replace("{context}", context_text).replace("{question}", question)

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]
