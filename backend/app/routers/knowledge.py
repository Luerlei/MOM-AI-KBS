"""知识管理路由"""
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import UPLOAD_PATH
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, BatchOperation
from app.services import knowledge_service
from app.utils.response import success, page_result, APIError

router = APIRouter()


@router.get("")
def list_knowledge(
    page: int = 1,
    page_size: int = 10,
    category_id: Optional[int] = None,
    tag_ids: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """知识列表（分页、筛选）"""
    tag_id_list = None
    if tag_ids:
        try:
            tag_id_list = [int(x) for x in tag_ids.split(",") if x.strip()]
        except ValueError:
            tag_id_list = None
    items, total = knowledge_service.get_list(
        db, page=page, page_size=page_size, category_id=category_id,
        tag_ids=tag_id_list, keyword=keyword,
    )
    return page_result(items, total, page, page_size)


@router.get("/{kid}")
def get_knowledge(kid: int, db: Session = Depends(get_db)):
    """知识详情"""
    k = knowledge_service.get_by_id(db, kid)
    out = knowledge_service._to_out(k)
    out["documents"] = [
        {"id": d.id, "filename": d.filename, "file_type": d.file_type, "file_size": d.file_size}
        for d in k.documents
    ]
    return success(out)


@router.post("")
def create_knowledge(data: KnowledgeCreate, db: Session = Depends(get_db)):
    """创建知识"""
    k = knowledge_service.create(db, data)
    return success(knowledge_service._to_out(k), message="创建成功")


@router.put("/{kid}")
def update_knowledge(kid: int, data: KnowledgeUpdate, db: Session = Depends(get_db)):
    """更新知识"""
    k = knowledge_service.update(db, kid, data)
    return success(knowledge_service._to_out(k), message="更新成功")


@router.delete("/{kid}")
def delete_knowledge(kid: int, db: Session = Depends(get_db)):
    """删除知识"""
    knowledge_service.delete(db, kid)
    return success(message="删除成功")


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """批量上传文件"""
    if not files:
        raise APIError("请选择要上传的文件")
    created = knowledge_service.upload_files(db, files)
    return success([knowledge_service._to_out(k) for k in created], message=f"成功上传 {len(created)} 个文件")


@router.post("/batch")
def batch_operation(data: BatchOperation, db: Session = Depends(get_db)):
    """批量操作"""
    knowledge_service.batch_operation(db, data)
    return success(message="批量操作成功")


@router.get("/{kid}/related")
def get_related(kid: int, limit: int = 5, db: Session = Depends(get_db)):
    """相关内容"""
    items = knowledge_service.get_related(db, kid, limit=limit)
    return success(items)


@router.post("/rebuild-indexes")
def rebuild_indexes(db: Session = Depends(get_db)):
    """重建所有知识的向量索引（切换 Embedding 模型后调用）"""
    result = knowledge_service.rebuild_all_indexes(db)
    return success(result, message=f"重建完成: 成功 {result['success']}/{result['total']}")


@router.get("/{kid}/documents/{doc_id}/download")
def download_document(kid: int, doc_id: int, db: Session = Depends(get_db)):
    """下载知识条目的附件"""
    from app.models import Document
    doc = db.query(Document).filter(Document.id == doc_id, Document.knowledge_id == kid).first()
    if not doc:
        raise APIError("附件不存在", status_code=404)
    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(UPLOAD_PATH, file_path)
    if not os.path.exists(file_path):
        raise APIError("文件不存在或已删除", status_code=404)
    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/octet-stream",
    )
