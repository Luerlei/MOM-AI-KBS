"""Token 统计路由"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TokenUsage, QAHistory
from app.utils.response import success, page_result, APIError
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


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

    # 使用 SQL 聚合替代 Python 循环
    from app.models import Skill

    # 总计：SQL 聚合
    total_agg = db.query(
        func.sum(TokenUsage.input_tokens).label("total_input"),
        func.sum(TokenUsage.output_tokens).label("total_output"),
        func.count(TokenUsage.id).label("call_count"),
    ).filter(TokenUsage.created_at >= start_str)
    if skill_id:
        total_agg = total_agg.filter(TokenUsage.skill_id == skill_id)
    if model_name:
        total_agg = total_agg.filter(TokenUsage.model_name == model_name)
    agg_row = total_agg.one()
    total_input = int(agg_row.total_input or 0)
    total_output = int(agg_row.total_output or 0)
    total_tokens = total_input + total_output
    call_count = int(agg_row.call_count or 0)

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

    # 趋势数据：SQL 按天分组聚合（created_at 是字符串 ISO 格式，取前 10 位为日期）
    day_expr = func.substr(TokenUsage.created_at, 1, 10)
    trend_q = db.query(
        day_expr.label("day"),
        func.sum(TokenUsage.input_tokens).label("input_tokens"),
        func.sum(TokenUsage.output_tokens).label("output_tokens"),
        func.count(TokenUsage.id).label("calls"),
    ).filter(TokenUsage.created_at >= start_str)
    if skill_id:
        trend_q = trend_q.filter(TokenUsage.skill_id == skill_id)
    if model_name:
        trend_q = trend_q.filter(TokenUsage.model_name == model_name)
    trend_q = trend_q.group_by(day_expr).order_by(day_expr)
    trend_list = []
    for row in trend_q.all():
        day = row.day or "unknown"
        in_t = int(row.input_tokens or 0)
        out_t = int(row.output_tokens or 0)
        trend_list.append({
            "date": day,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": in_t + out_t,
            "calls": int(row.calls or 0),
        })

    # 按 Skill 分布：SQL 聚合
    skill_q = db.query(
        TokenUsage.skill_id.label("sid"),
        func.sum(TokenUsage.input_tokens).label("input_tokens"),
        func.sum(TokenUsage.output_tokens).label("output_tokens"),
        func.count(TokenUsage.id).label("calls"),
    ).filter(TokenUsage.created_at >= start_str)
    if skill_id:
        skill_q = skill_q.filter(TokenUsage.skill_id == skill_id)
    if model_name:
        skill_q = skill_q.filter(TokenUsage.model_name == model_name)
    skill_q = skill_q.group_by(TokenUsage.skill_id)
    skill_map = {s.id: s.name for s in db.query(Skill).all()}
    by_skill_list = []
    for row in skill_q.all():
        sid = row.sid or 0
        in_t = int(row.input_tokens or 0)
        out_t = int(row.output_tokens or 0)
        by_skill_list.append({
            "skill_id": sid,
            "skill_name": skill_map.get(sid, "未知"),
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": in_t + out_t,
            "calls": int(row.calls or 0),
        })

    # 按调用类型分布：SQL 聚合
    ct_q = db.query(
        TokenUsage.call_type.label("ct"),
        func.sum(TokenUsage.input_tokens).label("input_tokens"),
        func.sum(TokenUsage.output_tokens).label("output_tokens"),
        func.count(TokenUsage.id).label("calls"),
    ).filter(TokenUsage.created_at >= start_str)
    if skill_id:
        ct_q = ct_q.filter(TokenUsage.skill_id == skill_id)
    if model_name:
        ct_q = ct_q.filter(TokenUsage.model_name == model_name)
    ct_q = ct_q.group_by(TokenUsage.call_type)
    by_call_type_list = []
    for row in ct_q.all():
        ct = row.ct or "unknown"
        in_t = int(row.input_tokens or 0)
        out_t = int(row.output_tokens or 0)
        by_call_type_list.append({
            "call_type": ct,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": in_t + out_t,
            "calls": int(row.calls or 0),
        })

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
        "cost_estimate": _estimate_cost(db, start_str, skill_id, model_name),
    })


def _estimate_cost(db, start_str: str, skill_id: int = None, model_name: str = None) -> dict:
    """基于模型单价估算 Token 成本（元）"""
    from app.models import ModelConfig as MC
    # 加载所有模型的价格配置
    models = db.query(MC).all()
    price_map = {}
    for m in models:
        price_map[m.model_name] = {
            "input_price": m.input_price or 0.0,
            "output_price": m.output_price or 0.0,
        }

    # 按模型名聚合 Token 使用量（应用筛选条件）
    model_agg = db.query(
        TokenUsage.model_name.label("mn"),
        func.sum(TokenUsage.input_tokens).label("in_t"),
        func.sum(TokenUsage.output_tokens).label("out_t"),
    ).filter(TokenUsage.created_at >= start_str)
    if skill_id:
        model_agg = model_agg.filter(TokenUsage.skill_id == skill_id)
    if model_name:
        model_agg = model_agg.filter(TokenUsage.model_name == model_name)
    model_agg = model_agg.group_by(TokenUsage.model_name)

    total_cost = 0.0
    by_model = []
    for row in model_agg.all():
        mn = row.mn or "unknown"
        in_t = int(row.in_t or 0)
        out_t = int(row.out_t or 0)
        prices = price_map.get(mn, {"input_price": 0.0, "output_price": 0.0})
        cost = (in_t / 1000.0) * prices["input_price"] + (out_t / 1000.0) * prices["output_price"]
        total_cost += cost
        if cost > 0 or in_t > 0 or out_t > 0:
            by_model.append({
                "model_name": mn,
                "input_tokens": in_t,
                "output_tokens": out_t,
                "cost": round(cost, 4),
            })

    return {
        "total_cost": round(total_cost, 4),
        "by_model": by_model,
    }


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
        # created_at 存储为 ISO 格式（T 分隔符），用 T23:59:59 避免当天数据丢失
        q = q.filter(QAHistory.created_at <= end_date + "T23:59:59")
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
        # created_at 存储为 ISO 格式（T 分隔符），用 T23:59:59 避免当天数据丢失
        q = q.filter(TokenUsage.created_at <= end_date + "T23:59:59")
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
