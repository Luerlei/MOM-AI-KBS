"""Skill 管理路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.skill import SkillCreate, SkillUpdate, SkillTestRequest
from app.services import skill_service, skill_router
from app.utils.response import success, APIError
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("")
def list_skills(
    category: str = None,
    function: str = None,
    enabled: str = None,
    db: Session = Depends(get_db),
):
    """Skill 列表"""
    enabled_val = None
    if enabled is not None and enabled != "":
        enabled_val = enabled.lower() == "true"
    items = skill_service.get_list(db, category=category, function=function, enabled=enabled_val)
    return success(items)


@router.get("/templates")
def get_templates():
    """模板列表"""
    return success(skill_service.get_templates())


@router.get("/{sid}")
def get_skill(sid: int, db: Session = Depends(get_db)):
    """Skill 详情"""
    s = skill_service.get_by_id(db, sid)
    return success(skill_service._to_out(s))


@router.post("")
def create_skill(data: SkillCreate, db: Session = Depends(get_db)):
    """创建 Skill"""
    s = skill_service.create(db, data)
    return success(skill_service._to_out(s), message="创建成功")


@router.post("/from-template")
def create_from_template(template_id: str = "", db: Session = Depends(get_db)):
    """从模板创建"""
    if not template_id:
        raise APIError("请提供 template_id")
    s = skill_service.create_from_template(db, template_id)
    return success(skill_service._to_out(s), message="从模板创建成功")


@router.put("/{sid}")
def update_skill(sid: int, data: SkillUpdate, db: Session = Depends(get_db)):
    """更新 Skill"""
    s = skill_service.update(db, sid, data)
    return success(skill_service._to_out(s), message="更新成功")


@router.delete("/{sid}")
def delete_skill(sid: int, db: Session = Depends(get_db)):
    """删除 Skill"""
    skill_service.delete(db, sid)
    return success(message="删除成功")


@router.put("/{sid}/toggle")
def toggle_skill(sid: int, db: Session = Depends(get_db)):
    """启用/禁用"""
    s = skill_service.toggle(db, sid)
    return success(skill_service._to_out(s), message="切换成功")


@router.post("/{sid}/test")
async def test_skill(sid: int, data: SkillTestRequest, db: Session = Depends(get_db)):
    """测试 Skill 路由"""
    # 确认 Skill 存在
    skill_service.get_by_id(db, sid)
    result = await skill_router.test_route(data.question, db)
    return success({
        "matched_skill": result.matched_skill,
        "match_type": result.match_type,
        "score": result.score,
        "all_scores": result.all_scores,
    })
