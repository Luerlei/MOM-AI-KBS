"""Skill 管理服务"""
import json

from app.models import Skill
from app.schemas.skill import SkillCreate, SkillUpdate
from app.utils.response import APIError


def _invalidate_skill_cache():
    """清除 Skill description embedding 缓存（修改 Skill 后调用）"""
    try:
        from app.services.skill_router import _skill_embedding_cache
        _skill_embedding_cache.clear()
    except Exception:
        pass


# 预设 Skill 模板
SKILL_TEMPLATES = [
    {
        "id": "tpl_fault_diagnosis",
        "name": "故障诊断",
        "description": "针对设备故障、报警、错误代码进行诊断和处理建议",
        "category": "设备管理",
        "function": "故障诊断",
        "trigger_keywords": ["故障", "报错", "异常", "错误代码", "E0", "E1"],
        "trigger_patterns": [r"E\d+", r"故障代码.*", r".*报警.*"],
        "prompt_template": "你是MOM系统设备故障诊断专家。请根据设备故障现象和知识库内容，给出诊断结论和处理建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 故障现象分析\n2. 可能原因\n3. 处理建议\n4. 注意事项",
        "knowledge_scope": {"category_ids": [4], "tag_ids": [1]},
    },
    {
        "id": "tpl_maintenance",
        "name": "保养维护",
        "description": "设备保养计划、维护周期、润滑等维护知识",
        "category": "设备管理",
        "function": "保养维护",
        "trigger_keywords": ["保养", "维护", "检修", "周期", "润滑"],
        "trigger_patterns": [r"保养.*", r"维护.*周期"],
        "prompt_template": "你是MOM系统设备保养维护专家。请根据保养需求和相关知识，给出维护方案和注意事项。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 保养项目\n2. 维护标准\n3. 周期建议\n4. 安全注意事项",
        "knowledge_scope": {"category_ids": [4], "tag_ids": [2]},
    },
    {
        "id": "tpl_process",
        "name": "工艺指导",
        "description": "生产工艺、工序参数、操作规程等指导",
        "category": "制造运营",
        "function": "工艺指导",
        "trigger_keywords": ["工艺", "工序", "参数", "操作规程", "加工"],
        "trigger_patterns": [r"工艺.*", r"加工.*参数"],
        "prompt_template": "你是MOM系统工艺指导专家。请根据工艺问题给出操作指导和参数建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 工艺要求\n2. 关键参数\n3. 操作步骤\n4. 质量控制点",
        "knowledge_scope": {"category_ids": [1]},
    },
    {
        "id": "tpl_quality",
        "name": "质量检验",
        "description": "质量标准、检验方法、合格判定等质量知识",
        "category": "质量管理",
        "function": "质量检验",
        "trigger_keywords": ["质量", "检验", "合格", "不合格", "标准", "偏差"],
        "trigger_patterns": [r"质量.*标准", r"检验.*"],
        "prompt_template": "你是MOM系统质量管理专家。请根据质量检验问题给出判定结果和处理建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 质量标准\n2. 检验方法\n3. 判定结论\n4. 处理建议",
        "knowledge_scope": {"category_ids": [3]},
    },
    {
        "id": "tpl_general",
        "name": "通用问答",
        "description": "通用知识问答，未命中其他Skill时使用",
        "category": "通用",
        "function": "通用问答",
        "trigger_keywords": [],
        "trigger_patterns": [],
        "prompt_template": "你是MOM系统AI知识库助手。请根据以下知识上下文回答用户问题。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请基于上述上下文回答，若上下文不足请如实说明。",
        "knowledge_scope": {},
    },
]


def _to_out(s: Skill) -> dict:
    """转输出格式（解析 JSON 字段）"""
    try:
        kw = json.loads(s.trigger_keywords) if s.trigger_keywords else []
    except Exception:
        kw = []
    try:
        pt = json.loads(s.trigger_patterns) if s.trigger_patterns else []
    except Exception:
        pt = []
    try:
        scope = json.loads(s.knowledge_scope) if s.knowledge_scope else {}
    except Exception:
        scope = {}
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category": s.category,
        "function": s.function,
        "trigger_keywords": kw,
        "trigger_patterns": pt,
        "prompt_template": s.prompt_template,
        "knowledge_scope": scope,
        "enabled": s.enabled,
        "is_default": s.is_default,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def get_list(db, category: str = None, function: str = None, enabled: bool = None) -> list:
    """获取 Skill 列表"""
    q = db.query(Skill)
    if category:
        q = q.filter(Skill.category == category)
    if function:
        q = q.filter(Skill.function == function)
    if enabled is not None:
        q = q.filter(Skill.enabled == enabled)
    items = q.order_by(Skill.id).all()
    return [_to_out(s) for s in items]


def get_by_id(db, id: int) -> Skill:
    s = db.query(Skill).filter(Skill.id == id).first()
    if not s:
        raise APIError("Skill不存在", status_code=404)
    return s


def create(db, data: SkillCreate) -> Skill:
    """创建 Skill"""
    s = Skill(
        name=data.name,
        description=data.description,
        category=data.category,
        function=data.function,
        trigger_keywords=json.dumps(data.trigger_keywords, ensure_ascii=False),
        trigger_patterns=json.dumps(data.trigger_patterns, ensure_ascii=False),
        prompt_template=data.prompt_template,
        knowledge_scope=json.dumps(data.knowledge_scope, ensure_ascii=False),
        enabled=data.enabled,
        is_default=data.is_default,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    _invalidate_skill_cache()
    return s


def update(db, id: int, data: SkillUpdate) -> Skill:
    """更新 Skill"""
    s = get_by_id(db, id)
    if data.name is not None:
        s.name = data.name
    if data.description is not None:
        s.description = data.description
    if data.category is not None:
        s.category = data.category
    if data.function is not None:
        s.function = data.function
    if data.trigger_keywords is not None:
        s.trigger_keywords = json.dumps(data.trigger_keywords, ensure_ascii=False)
    if data.trigger_patterns is not None:
        s.trigger_patterns = json.dumps(data.trigger_patterns, ensure_ascii=False)
    if data.prompt_template is not None:
        s.prompt_template = data.prompt_template
    if data.knowledge_scope is not None:
        s.knowledge_scope = json.dumps(data.knowledge_scope, ensure_ascii=False)
    if data.enabled is not None:
        s.enabled = data.enabled
    db.commit()
    db.refresh(s)
    _invalidate_skill_cache()
    return s


def delete(db, id: int):
    """删除 Skill（默认 Skill 不允许删除）"""
    s = get_by_id(db, id)
    if s.is_default:
        raise APIError("默认Skill不允许删除", status_code=400)
    db.delete(s)
    db.commit()
    _invalidate_skill_cache()


def toggle(db, id: int) -> Skill:
    """启用/禁用切换"""
    s = get_by_id(db, id)
    if s.is_default:
        raise APIError("默认Skill不能被禁用", status_code=400)
    s.enabled = not s.enabled
    db.commit()
    db.refresh(s)
    _invalidate_skill_cache()
    return s


def get_templates() -> list:
    """返回预设 Skill 模板列表"""
    return [{"id": t["id"], "name": t["name"], "description": t["description"],
             "category": t["category"], "function": t["function"]} for t in SKILL_TEMPLATES]


def create_from_template(db, template_id: str) -> Skill:
    """从模板创建 Skill"""
    tpl = None
    for t in SKILL_TEMPLATES:
        if t["id"] == template_id:
            tpl = t
            break
    if not tpl:
        raise APIError("模板不存在", status_code=404)
    # 排除 id 字段构造 SkillCreate
    data = SkillCreate(
        name=tpl["name"],
        description=tpl["description"],
        category=tpl["category"],
        function=tpl["function"],
        trigger_keywords=tpl["trigger_keywords"],
        trigger_patterns=tpl["trigger_patterns"],
        prompt_template=tpl["prompt_template"],
        knowledge_scope=tpl["knowledge_scope"],
        enabled=True,
        is_default=(tpl["id"] == "tpl_general"),
    )
    return create(db, data)
