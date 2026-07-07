"""Skill 选项管理服务"""
from app.models import SkillOption
from app.schemas.skill_option import SkillOptionCreate, SkillOptionUpdate
from app.utils.response import APIError


# 预制选项
INITIAL_OPTIONS = [
    # 模块维度
    {"type": "category", "name": "制造运营", "description": "生产制造相关", "sort_order": 1, "color": "blue"},
    {"type": "category", "name": "仓储物流", "description": "仓储与物流管理", "sort_order": 2, "color": "cyan"},
    {"type": "category", "name": "质量管理", "description": "质量检验与标准", "sort_order": 3, "color": "green"},
    {"type": "category", "name": "设备管理", "description": "设备维护与故障", "sort_order": 4, "color": "orange"},
    {"type": "category", "name": "通用", "description": "通用类别", "sort_order": 99, "color": "default"},
    # 功能维度
    {"type": "function", "name": "故障诊断", "description": "设备故障诊断", "sort_order": 1, "color": "red"},
    {"type": "function", "name": "保养维护", "description": "设备保养", "sort_order": 2, "color": "orange"},
    {"type": "function", "name": "工艺指导", "description": "工艺参数指导", "sort_order": 3, "color": "blue"},
    {"type": "function", "name": "质量检验", "description": "质量检验", "sort_order": 4, "color": "green"},
    {"type": "function", "name": "通用问答", "description": "通用问答", "sort_order": 99, "color": "default"},
]


def _to_out(o: SkillOption) -> dict:
    return {
        "id": o.id,
        "type": o.type,
        "name": o.name,
        "description": o.description,
        "sort_order": o.sort_order,
        "color": o.color,
        "created_at": o.created_at,
    }


def get_list(db, opt_type: str = None) -> list:
    """获取选项列表"""
    q = db.query(SkillOption)
    if opt_type:
        q = q.filter(SkillOption.type == opt_type)
    items = q.order_by(SkillOption.sort_order, SkillOption.id).all()
    return [_to_out(o) for o in items]


def create(db, data: SkillOptionCreate) -> SkillOption:
    """创建选项"""
    existing = db.query(SkillOption).filter(
        SkillOption.type == data.type,
        SkillOption.name == data.name,
    ).first()
    if existing:
        raise APIError(f"该{('分类' if data.type == 'category' else '功能')}已存在", status_code=400)
    o = SkillOption(
        type=data.type,
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
        color=data.color,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def update(db, id: int, data: SkillOptionUpdate) -> SkillOption:
    """更新选项"""
    o = db.query(SkillOption).filter(SkillOption.id == id).first()
    if not o:
        raise APIError("选项不存在", status_code=404)
    if data.name is not None:
        existing = db.query(SkillOption).filter(
            SkillOption.type == o.type,
            SkillOption.name == data.name,
            SkillOption.id != id,
        ).first()
        if existing:
            raise APIError("该名称已存在", status_code=400)
        o.name = data.name
    if data.description is not None:
        o.description = data.description
    if data.sort_order is not None:
        o.sort_order = data.sort_order
    if data.color is not None:
        o.color = data.color
    db.commit()
    db.refresh(o)
    return o


def delete(db, id: int):
    """删除选项"""
    o = db.query(SkillOption).filter(SkillOption.id == id).first()
    if not o:
        raise APIError("选项不存在", status_code=404)
    db.delete(o)
    db.commit()


def seed_options(db):
    """初始化预制选项（仅在表为空时创建）"""
    count = db.query(SkillOption).count()
    if count > 0:
        return
    for opt in INITIAL_OPTIONS:
        o = SkillOption(
            type=opt["type"],
            name=opt["name"],
            description=opt.get("description", ""),
            sort_order=opt.get("sort_order", 0),
            color=opt.get("color", "default"),
        )
        db.add(o)
    db.commit()
