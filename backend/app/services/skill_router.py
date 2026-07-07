"""Skill 路由引擎（核心）：三级匹配"""
import json
import re

from app.models import Skill
from app.schemas.skill import SkillTestResult
from app.utils.response import APIError
from app.services.skill_service import _to_out


def _parse_keywords(skill: Skill) -> list:
    try:
        return json.loads(skill.trigger_keywords) if skill.trigger_keywords else []
    except Exception:
        return []


def _parse_patterns(skill: Skill) -> list:
    try:
        return json.loads(skill.trigger_patterns) if skill.trigger_patterns else []
    except Exception:
        return []


def route(question: str, db):
    """三级匹配路由

    Returns:
        (Skill, match_type, score)
    """
    skills = db.query(Skill).filter(Skill.enabled == True).all()  # noqa: E712
    if not skills:
        raise APIError("没有可用的Skill，请先创建或启用Skill", status_code=400)

    # 1. 关键词 / 正则匹配
    keyword_hits = []  # [(skill, hit_count)]
    for s in skills:
        kws = _parse_keywords(s)
        pts = _parse_patterns(s)
        hit_count = 0
        for kw in kws:
            if kw and kw in question:
                hit_count += 1
        for pt in pts:
            try:
                if re.search(pt, question):
                    hit_count += 1
            except re.error:
                continue
        if hit_count > 0:
            keyword_hits.append((s, hit_count))

    if keyword_hits:
        # 取命中数最多的
        keyword_hits.sort(key=lambda x: x[1], reverse=True)
        best_skill, best_hits = keyword_hits[0]
        return best_skill, "keyword", float(best_hits)

    # 2. 语义匹配
    semantic_result = _semantic_route(question, skills)
    if semantic_result:
        return semantic_result

    # 3. 默认兜底
    default_skill = next((s for s in skills if s.is_default), None)
    if not default_skill:
        # 没有 default 则返回第一个
        default_skill = skills[0]
    return default_skill, "default", 0.0


def _semantic_route(question: str, skills: list):
    """语义匹配：将问题 Embedding，与每个 Skill 的 description Embedding 计算相似度"""
    try:
        from app.services.llm_client import model_manager
        from app.services.embedding_service import embedding_service
        from app.services.knowledge_service import _run_async

        # 检查是否有启用的 Embedding 模型
        try:
            model_manager.get_active_embedding()
        except APIError:
            return None

        # 准备文本：问题 + 各 Skill 的 description
        descs = [s.description or s.name for s in skills]
        texts = [question] + descs
        vecs = _run_async(embedding_service.embed(texts, source="skill_router"))
        if not vecs or len(vecs) != len(texts):
            return None

        q_vec = vecs[0]
        best_score = 0.0
        best_skill = None
        for i, s in enumerate(skills):
            d_vec = vecs[i + 1]
            score = _cosine(q_vec, d_vec)
            if score > best_score:
                best_score = score
                best_skill = s

        # 阈值 > 0.7
        if best_skill and best_score > 0.7:
            return best_skill, "semantic", best_score
        return None
    except APIError:
        return None
    except Exception:
        return None


def _cosine(a: list, b: list) -> float:
    """计算余弦相似度"""
    if not a or not b or len(a) != len(b):
        return 0.0
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def test_route(question: str, db) -> SkillTestResult:
    """测试路由结果，返回所有 Skill 的得分"""
    skills = db.query(Skill).filter(Skill.enabled == True).all()  # noqa: E712
    all_scores = []

    # 关键词得分
    for s in skills:
        kws = _parse_keywords(s)
        pts = _parse_patterns(s)
        hit = 0
        for kw in kws:
            if kw and kw in question:
                hit += 1
        for pt in pts:
            try:
                if re.search(pt, question):
                    hit += 1
            except re.error:
                continue
        all_scores.append({
            "skill_id": s.id,
            "skill_name": s.name,
            "keyword_hits": hit,
            "semantic_score": 0.0,
        })

    # 路由
    matched, match_type, score = route(question, db)
    return SkillTestResult(
        matched_skill=_to_out(matched),
        match_type=match_type,
        score=score,
        all_scores=all_scores,
    )
