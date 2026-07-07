"""预制数据初始化服务"""
import json

from app.database import SessionLocal
from app.models import Category, Tag, Skill
from app.services.skill_option_service import seed_options


# 分类定义：(id, name)
INITIAL_CATEGORIES = [
    (1, "制造运营"),
    (2, "仓储物流"),
    (3, "质量管理"),
    (4, "设备管理"),
]

# 标签定义
INITIAL_TAGS = [
    "故障代码", "保养", "工艺", "质量标准", "仓储管理", "操作经验",
]

# 预制 Skill 定义
INITIAL_SKILLS = [
    {
        "name": "故障诊断",
        "description": "针对设备故障、报警、错误代码进行诊断和处理建议",
        "category": "设备管理",
        "function": "故障诊断",
        "trigger_keywords": ["故障", "报错", "异常", "错误代码", "E0", "E1"],
        "trigger_patterns": [r"E\d+", r"故障代码.*", r".*报警.*"],
        "prompt_template": "你是MOM系统设备故障诊断专家。请根据设备故障现象和知识库内容，给出诊断结论和处理建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 故障现象分析\n2. 可能原因\n3. 处理建议\n4. 注意事项",
        "knowledge_scope": {"category_ids": [4], "tag_ids": [1]},
        "is_default": False,
    },
    {
        "name": "保养维护",
        "description": "设备保养计划、维护周期、润滑等维护知识",
        "category": "设备管理",
        "function": "保养维护",
        "trigger_keywords": ["保养", "维护", "检修", "周期", "润滑"],
        "trigger_patterns": [r"保养.*", r"维护.*周期"],
        "prompt_template": "你是MOM系统设备保养维护专家。请根据保养需求和相关知识，给出维护方案和注意事项。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 保养项目\n2. 维护标准\n3. 周期建议\n4. 安全注意事项",
        "knowledge_scope": {"category_ids": [4], "tag_ids": [2]},
        "is_default": False,
    },
    {
        "name": "工艺指导",
        "description": "生产工艺、工序参数、操作规程等指导",
        "category": "制造运营",
        "function": "工艺指导",
        "trigger_keywords": ["工艺", "工序", "参数", "操作规程", "加工"],
        "trigger_patterns": [r"工艺.*", r"加工.*参数"],
        "prompt_template": "你是MOM系统工艺指导专家。请根据工艺问题给出操作指导和参数建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 工艺要求\n2. 关键参数\n3. 操作步骤\n4. 质量控制点",
        "knowledge_scope": {"category_ids": [1]},
        "is_default": False,
    },
    {
        "name": "质量检验",
        "description": "质量标准、检验方法、合格判定等质量知识",
        "category": "质量管理",
        "function": "质量检验",
        "trigger_keywords": ["质量", "检验", "合格", "不合格", "标准", "偏差"],
        "trigger_patterns": [r"质量.*标准", r"检验.*"],
        "prompt_template": "你是MOM系统质量管理专家。请根据质量检验问题给出判定结果和处理建议。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请按以下结构回答：\n1. 质量标准\n2. 检验方法\n3. 判定结论\n4. 处理建议",
        "knowledge_scope": {"category_ids": [3]},
        "is_default": False,
    },
    {
        "name": "通用问答",
        "description": "通用知识问答，未命中其他Skill时使用",
        "category": "通用",
        "function": "通用问答",
        "trigger_keywords": [],
        "trigger_patterns": [],
        "prompt_template": "你是MOM系统AI知识库助手。请根据以下知识上下文回答用户问题。\n\n知识上下文：\n{context}\n\n用户问题：{question}\n\n请基于上述上下文回答，若上下文不足请如实说明。",
        "knowledge_scope": {},
        "is_default": True,
    },
]


def seed_initial_data():
    """系统启动时调用：创建预制数据（仅在不存在时创建）"""
    db = SessionLocal()
    try:
        # 1. 创建分类
        for cid, cname in INITIAL_CATEGORIES:
            existing = db.query(Category).filter(Category.id == cid).first()
            if not existing:
                c = Category(id=cid, name=cname, sort_order=cid)
                db.add(c)
        db.commit()

        # 2. 创建标签
        for tname in INITIAL_TAGS:
            existing = db.query(Tag).filter(Tag.name == tname).first()
            if not existing:
                t = Tag(name=tname)
                db.add(t)
        db.commit()

        # 3. 创建预制 Skill
        for sdef in INITIAL_SKILLS:
            existing = db.query(Skill).filter(Skill.name == sdef["name"]).first()
            if not existing:
                s = Skill(
                    name=sdef["name"],
                    description=sdef["description"],
                    category=sdef["category"],
                    function=sdef["function"],
                    trigger_keywords=json.dumps(sdef["trigger_keywords"], ensure_ascii=False),
                    trigger_patterns=json.dumps(sdef["trigger_patterns"], ensure_ascii=False),
                    prompt_template=sdef["prompt_template"],
                    knowledge_scope=json.dumps(sdef["knowledge_scope"], ensure_ascii=False),
                    enabled=True,
                    is_default=sdef["is_default"],
                )
                db.add(s)
        db.commit()

        # 4. 创建预制 Skill 分类/功能选项
        seed_options(db)
    except Exception as e:
        # 初始化失败不应阻塞启动
        print(f"[seed] 初始化预制数据时出错: {e}")
        db.rollback()
    finally:
        db.close()
