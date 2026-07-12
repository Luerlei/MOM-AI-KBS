"""Skill 路由引擎（核心）：三级匹配"""
import hashlib
import json
import logging
import re

from app.models import Skill
from app.schemas.skill import SkillTestResult
from app.utils.response import APIError
from app.services.skill_service import _to_out

logger = logging.getLogger(__name__)

# Skill description embedding 缓存：{cache_key: (embedding,)}
# cache_key = md5(description) 避免每次路由都重新向量化所有 Skill
_skill_embedding_cache: dict = {}


def _parse_keywords(skill: Skill) -> list:
    try:
        return json.loads(skill.trigger_keywords) if skill.trigger_keywords else []
    except Exception:
        logger.exception(f"[skill_router] 解析 trigger_keywords 失败 skill_id={skill.id}")
        return []


def _parse_patterns(skill: Skill) -> list:
    try:
        return json.loads(skill.trigger_patterns) if skill.trigger_patterns else []
    except Exception:
        logger.exception(f"[skill_router] 解析 trigger_patterns 失败 skill_id={skill.id}")
        return []


def _keyword_match(question: str, skills: list):
    """关键词 / 正则匹配

    Returns:
        (skill, hit_count) or None
    """
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
        keyword_hits.sort(key=lambda x: x[1], reverse=True)
        return keyword_hits[0]
    return None


async def route(question: str, db):
    """三级匹配路由（async：语义匹配走 await）

    Returns:
        (Skill, match_type, score)
    """
    skills = db.query(Skill).filter(Skill.enabled == True).all()  # noqa: E712
    if not skills:
        raise APIError("没有可用的Skill，请先创建或启用Skill", status_code=400)

    # 1. 关键词 / 正则匹配
    kw_result = _keyword_match(question, skills)
    if kw_result:
        best_skill, best_hits = kw_result
        return best_skill, "keyword", float(best_hits)

    # 2. 语义匹配
    semantic_result = await _semantic_route(question, skills)
    if semantic_result:
        return semantic_result

    # 3. 默认兜底
    default_skill = next((s for s in skills if s.is_default), None)
    if not default_skill:
        default_skill = skills[0]
    return default_skill, "default", 0.0


async def _semantic_route(question: str, skills: list):
    """语义匹配：将问题 Embedding，与每个 Skill 的 description Embedding 计算相似度

    使用缓存避免每次路由都重新向量化所有 Skill description。
    """
    try:
        from app.services.llm_client import model_manager
        from app.services.embedding_service import embedding_service

        # 检查是否有启用的 Embedding 模型
        try:
            model_manager.get_active_embedding()
        except APIError:
            return None

        # 问题需要每次向量化
        q_vecs = await embedding_service.embed([question], source="skill_router")
        if not q_vecs:
            return None
        q_vec = q_vecs[0]

        # Skill description 走缓存
        descs_to_embed = []  # [(skill, cache_key, description)]
        desc_vecs_map = {}  # cache_key -> embedding
        for s in skills:
            desc = s.description or s.name
            cache_key = hashlib.md5(desc.encode("utf-8")).hexdigest()
            if cache_key in _skill_embedding_cache:
                desc_vecs_map[cache_key] = _skill_embedding_cache[cache_key]
            else:
                descs_to_embed.append((s, cache_key, desc))

        # 批量向量化未缓存的 description
        if descs_to_embed:
            texts = [d[2] for d in descs_to_embed]
            vecs = await embedding_service.embed(texts, source="skill_router")
            if vecs and len(vecs) == len(texts):
                for (s, cache_key, _), vec in zip(descs_to_embed, vecs):
                    _skill_embedding_cache[cache_key] = vec
                    desc_vecs_map[cache_key] = vec

        # 计算相似度
        best_score = 0.0
        best_skill = None
        for s in skills:
            desc = s.description or s.name
            cache_key = hashlib.md5(desc.encode("utf-8")).hexdigest()
            d_vec = desc_vecs_map.get(cache_key)
            if not d_vec:
                continue
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
        logger.exception("[skill_router] 语义匹配失败")
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


async def test_route(question: str, db) -> SkillTestResult:
    """测试路由结果，返回所有 Skill 的得分（复用已计算的得分，避免重复 embedding）"""
    skills = db.query(Skill).filter(Skill.enabled == True).all()  # noqa: E712
    if not skills:
        raise APIError("没有可用的Skill，请先创建或启用Skill", status_code=400)

    all_scores = []
    kw_hits = {}  # skill_id -> hit_count

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
        kw_hits[s.id] = hit
        all_scores.append({
            "skill_id": s.id,
            "skill_name": s.name,
            "keyword_hits": hit,
            "semantic_score": 0.0,
        })

    # 语义得分（仅一次 embedding）
    sem_scores = await _compute_semantic_scores(question, skills)
    if sem_scores:
        for entry in all_scores:
            sid = entry["skill_id"]
            if sid in sem_scores:
                entry["semantic_score"] = round(sem_scores[sid], 4)

    # 复用已计算的得分确定路由结果（避免调用 route() 重复 embedding）
    # 1. 关键词匹配优先
    kw_matched = [(s, kw_hits[s.id]) for s in skills if kw_hits.get(s.id, 0) > 0]
    if kw_matched:
        kw_matched.sort(key=lambda x: x[1], reverse=True)
        matched = kw_matched[0][0]
        match_type = "keyword"
        score = float(kw_matched[0][1])
    # 2. 语义匹配（阈值 > 0.7）
    elif sem_scores:
        best_sid = max(sem_scores, key=lambda k: sem_scores[k])
        best_score = sem_scores[best_sid]
        if best_score > 0.7:
            matched = next(s for s in skills if s.id == best_sid)
            match_type = "semantic"
            score = best_score
        else:
            # 3. 默认兜底
            matched = next((s for s in skills if s.is_default), None) or skills[0]
            match_type = "default"
            score = 0.0
    else:
        # 3. 默认兜底
        matched = next((s for s in skills if s.is_default), None) or skills[0]
        match_type = "default"
        score = 0.0

    return SkillTestResult(
        matched_skill=_to_out(matched),
        match_type=match_type,
        score=score,
        all_scores=all_scores,
    )


async def _compute_semantic_scores(question: str, skills: list) -> dict:
    """为每个 Skill 计算与 question 的语义相似度，返回 {skill_id: score}"""
    try:
        from app.services.llm_client import model_manager
        from app.services.embedding_service import embedding_service

        # 检查是否有启用的 Embedding 模型
        try:
            model_manager.get_active_embedding()
        except APIError:
            return {}

        q_vecs = await embedding_service.embed([question], source="skill_router")
        if not q_vecs:
            return {}
        q_vec = q_vecs[0]

        # Skill description 走缓存
        descs_to_embed = []
        desc_vecs_map = {}
        for s in skills:
            desc = s.description or s.name
            cache_key = hashlib.md5(desc.encode("utf-8")).hexdigest()
            if cache_key in _skill_embedding_cache:
                desc_vecs_map[cache_key] = _skill_embedding_cache[cache_key]
            else:
                descs_to_embed.append((s, cache_key, desc))

        if descs_to_embed:
            texts = [d[2] for d in descs_to_embed]
            vecs = await embedding_service.embed(texts, source="skill_router")
            if vecs and len(vecs) == len(texts):
                for (s, cache_key, _), vec in zip(descs_to_embed, vecs):
                    _skill_embedding_cache[cache_key] = vec
                    desc_vecs_map[cache_key] = vec

        scores = {}
        for s in skills:
            desc = s.description or s.name
            cache_key = hashlib.md5(desc.encode("utf-8")).hexdigest()
            d_vec = desc_vecs_map.get(cache_key)
            if not d_vec:
                continue
            scores[s.id] = _cosine(q_vec, d_vec)
        return scores
    except APIError:
        return {}
    except Exception:
        logger.exception("[skill_router] 语义得分计算失败")
        return {}
