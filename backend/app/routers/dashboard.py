"""首页统计路由"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Knowledge, Skill, QAHistory, Document, ModelConfig
from app.utils.response import success
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


def _calc_start(time_range: str) -> Optional[str]:
    """根据 time_range 计算起始时间 ISO 字符串，None 表示不筛选"""
    now = datetime.utcnow()
    if time_range == "today":
        return (now - timedelta(hours=24)).isoformat()
    elif time_range == "week":
        return (now - timedelta(days=7)).isoformat()
    elif time_range == "month":
        return (now - timedelta(days=30)).isoformat()
    elif time_range == "all":
        return None
    return (now - timedelta(hours=24)).isoformat()


@router.get("/stats")
def stats(time_range: str = "today", db: Session = Depends(get_db)):
    """统计卡片数据

    Args:
        time_range: today / week / month / all，控制问答数量统计的时间范围
    """
    knowledge_count = db.query(Knowledge).count()
    skill_count = db.query(Skill).count()
    document_count = db.query(Document).count()
    model_count = db.query(ModelConfig).count()
    start_str = _calc_start(time_range)
    qa_q = db.query(QAHistory)
    if start_str:
        qa_q = qa_q.filter(QAHistory.created_at >= start_str)
    qa_count = qa_q.count()

    return success({
        "knowledge_count": knowledge_count,
        "skill_count": skill_count,
        "document_count": document_count,
        "today_qa_count": qa_count,
        "model_count": model_count,
    })


@router.get("/recent-qa")
def recent_qa(limit: int = 5, time_range: str = "today", db: Session = Depends(get_db)):
    """最近问答记录

    Args:
        time_range: today / week / month / all，筛选时间范围
    """
    start_str = _calc_start(time_range)
    q = db.query(QAHistory)
    if start_str:
        q = q.filter(QAHistory.created_at >= start_str)
    items = q.order_by(QAHistory.created_at.desc()).limit(limit).all()
    return success([
        {
            "id": h.id,
            "question": h.question,
            "answer_summary": (h.answer or "")[:100],
            "skill_name": h.skill_name,
            "created_at": h.created_at,
        }
        for h in items
    ])
