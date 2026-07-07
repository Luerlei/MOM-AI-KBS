"""Token 统计路由"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TokenUsage, QAHistory
from app.utils.response import success, page_result, APIError

router = APIRouter()


@router.get("")
def token_stats(
    time_range: str = "week",
    skill_id: int = None,
    model_name: str = None,
    db: Session = Depends(get_db),
):
    """Token 统计"""
    # 计算时间范围
    now = datetime.utcnow()
    if time_range == "today":
        start = now - timedelta(hours=24)
    elif time_range == "week":
        start = now - timedelta(days=7)
    elif time_range == "month":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=7)
    start_str = start.isoformat()

    q = db.query(TokenUsage).filter(TokenUsage.created_at >= start_str)
    if skill_id:
        q = q.filter(TokenUsage.skill_id == skill_id)
    if model_name:
        q = q.filter(TokenUsage.model_name == model_name)

    records = q.all()

    total_input = sum(r.input_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_tokens = total_input + total_output
    call_count = len(records)

    # 缓存命中率统计：缓存命中 = QAHistory中token_input=0且token_output=0的记录
    qa_q = db.query(QAHistory).filter(QAHistory.created_at >= start_str)
    if skill_id:
        qa_q = qa_q.filter(QAHistory.skill_id == skill_id)
    total_qa = qa_q.count()
    cache_hits = qa_q.filter(
        QAHistory.token_input == 0,
        QAHistory.token_output == 0,
    ).count()
    cache_hit_rate = round(cache_hits / total_qa * 100, 1) if total_qa > 0 else 0.0
    # 估算节省的token（缓存命中次数 × 平均token消耗）
    avg_tokens = total_tokens // call_count if call_count > 0 else 0
    tokens_saved = cache_hits * avg_tokens

    # 趋势数据（按天分组）
    trend = {}
    for r in records:
        try:
            day = r.created_at[:10] if r.created_at else "unknown"
        except Exception:
            day = "unknown"
        if day not in trend:
            trend[day] = {"date": day, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
        trend[day]["input_tokens"] += r.input_tokens
        trend[day]["output_tokens"] += r.output_tokens
        trend[day]["total_tokens"] += r.input_tokens + r.output_tokens
        trend[day]["calls"] += 1
    trend_list = sorted(trend.values(), key=lambda x: x["date"])

    # 按 Skill 分布
    by_skill = {}
    for r in records:
        sid = r.skill_id or 0
        if sid not in by_skill:
            by_skill[sid] = {"skill_id": sid, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
        by_skill[sid]["input_tokens"] += r.input_tokens
        by_skill[sid]["output_tokens"] += r.output_tokens
        by_skill[sid]["total_tokens"] += r.input_tokens + r.output_tokens
        by_skill[sid]["calls"] += 1
    # 关联 Skill 名称
    from app.models import Skill
    skill_map = {s.id: s.name for s in db.query(Skill).all()}
    by_skill_list = []
    for sid, v in by_skill.items():
        v["skill_name"] = skill_map.get(sid, "未知")
        by_skill_list.append(v)

    # 按调用类型分布
    by_call_type = {}
    for r in records:
        ct = r.call_type or "unknown"
        if ct not in by_call_type:
            by_call_type[ct] = {"call_type": ct, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
        by_call_type[ct]["input_tokens"] += r.input_tokens
        by_call_type[ct]["output_tokens"] += r.output_tokens
        by_call_type[ct]["total_tokens"] += r.input_tokens + r.output_tokens
        by_call_type[ct]["calls"] += 1
    by_call_type_list = list(by_call_type.values())

    return success({
        "total_tokens": total_tokens,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "call_count": call_count,
        "trend": trend_list,
        "by_skill": by_skill_list,
        "by_call_type": by_call_type_list,
        "cache_stats": {
            "total_qa": total_qa,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hit_rate,
            "tokens_saved": tokens_saved,
        },
    })


@router.get("/call-logs")
def call_logs(
    time_range: str = "week",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skill_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """调用日志列表（基于 QAHistory）"""
    now = datetime.utcnow()
    if time_range == "today":
        start = now - timedelta(hours=24)
    elif time_range == "week":
        start = now - timedelta(days=7)
    elif time_range == "month":
        start = now - timedelta(days=30)
    elif time_range == "custom" and start_date:
        start = datetime.fromisoformat(start_date)
    else:
        start = now - timedelta(days=7)
    start_str = start.isoformat()

    q = db.query(QAHistory).filter(QAHistory.created_at >= start_str)
    if end_date and time_range == "custom":
        q = q.filter(QAHistory.created_at <= end_date + " 23:59:59")
    if skill_id:
        q = q.filter(QAHistory.skill_id == skill_id)

    total = q.count()
    items = q.order_by(QAHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for h in items:
        cache_hit = h.token_input == 0 and h.token_output == 0
        result.append({
            "id": h.id,
            "question": (h.question or "")[:200],
            "skill_name": h.skill_name or "通用问答",
            "model_name": "",
            "input_tokens": h.token_input or 0,
            "output_tokens": h.token_output or 0,
            "total_tokens": (h.token_input or 0) + (h.token_output or 0),
            "cache_hit": cache_hit,
            "created_at": h.created_at,
        })

    return page_result(result, total, page, page_size)


@router.get("/model-call-logs")
def model_call_logs(
    time_range: str = "week",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    call_type: Optional[str] = None,
    model_name: Optional[str] = None,
    skill_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """模型调用日志列表（基于 TokenUsage 表，记录所有模型调用：chat/embedding/summary 等）"""
    now = datetime.utcnow()
    if time_range == "today":
        start = now - timedelta(hours=24)
    elif time_range == "week":
        start = now - timedelta(days=7)
    elif time_range == "month":
        start = now - timedelta(days=30)
    elif time_range == "custom" and start_date:
        start = datetime.fromisoformat(start_date)
    else:
        start = now - timedelta(days=7)
    start_str = start.isoformat()

    q = db.query(TokenUsage).filter(TokenUsage.created_at >= start_str)
    if end_date and time_range == "custom":
        q = q.filter(TokenUsage.created_at <= end_date + " 23:59:59")
    if call_type:
        q = q.filter(TokenUsage.call_type == call_type)
    if model_name:
        q = q.filter(TokenUsage.model_name.like(f"%{model_name}%"))
    if skill_id:
        q = q.filter(TokenUsage.skill_id == skill_id)

    total = q.count()
    items = q.order_by(TokenUsage.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 关联 Skill 与 QAHistory 信息
    from app.models import Skill
    skill_map = {s.id: s.name for s in db.query(Skill).all()}
    qa_ids = [i.qa_history_id for i in items if i.qa_history_id]
    qa_map = {}
    if qa_ids:
        qa_records = db.query(QAHistory).filter(QAHistory.id.in_(qa_ids)).all()
        qa_map = {q.id: q for q in qa_records}

    result = []
    for r in items:
        skill_name = skill_map.get(r.skill_id, "") if r.skill_id else ""
        question = ""
        if r.qa_history_id and r.qa_history_id in qa_map:
            question = (qa_map[r.qa_history_id].question or "")[:200]
        result.append({
            "id": r.id,
            "call_type": r.call_type or "unknown",
            "model_name": r.model_name or "",
            "skill_id": r.skill_id,
            "skill_name": skill_name,
            "qa_history_id": r.qa_history_id,
            "question": question,
            "input_tokens": r.input_tokens or 0,
            "output_tokens": r.output_tokens or 0,
            "total_tokens": (r.input_tokens or 0) + (r.output_tokens or 0),
            "duration_ms": r.duration_ms or 0,
            "source": getattr(r, "source", None) or "qa",
            "created_at": r.created_at,
        })

    return page_result(result, total, page, page_size)
