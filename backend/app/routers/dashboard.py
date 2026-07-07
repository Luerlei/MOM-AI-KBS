"""首页统计路由"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Knowledge, Skill, QAHistory, Document, ModelConfig
from app.utils.response import success

router = APIRouter()


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """统计卡片数据"""
    knowledge_count = db.query(Knowledge).count()
    skill_count = db.query(Skill).count()
    document_count = db.query(Document).count()
    model_count = db.query(ModelConfig).count()
    today_start = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    today_qa = db.query(QAHistory).filter(QAHistory.created_at >= today_start).count()

    return success({
        "knowledge_count": knowledge_count,
        "skill_count": skill_count,
        "document_count": document_count,
        "today_qa_count": today_qa,
        "model_count": model_count,
    })


@router.get("/recent-qa")
def recent_qa(limit: int = 5, db: Session = Depends(get_db)):
    """最近问答记录"""
    items = db.query(QAHistory).order_by(QAHistory.created_at.desc()).limit(limit).all()
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
