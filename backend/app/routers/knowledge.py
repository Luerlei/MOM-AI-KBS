"""知识管理路由"""
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import BASE_DIR
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, BatchOperation
from app.services import knowledge_service
from app.utils.response import success, page_result, APIError
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("")
def list_knowledge(
    page: int = 1,
    page_size: int = 10,
    category_id: Optional[int] = None,
    tag_ids: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
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
        tag_ids=tag_id_list, keyword=keyword, status=status,
    )
    return page_result(items, total, page, page_size)


@router.get("/{kid}")
def get_knowledge(kid: int, db: Session = Depends(get_db)):
    """知识详情"""
    k = knowledge_service.get_by_id(db, kid)
    out = knowledge_service._to_out(k, include_index_status=True)
    out["documents"] = [
        {"id": d.id, "filename": d.filename, "file_type": d.file_type, "file_size": d.file_size}
        for d in k.documents
    ]
    return success(out)


@router.post("")
async def create_knowledge(data: KnowledgeCreate, db: Session = Depends(get_db)):
    """创建知识"""
    k = await knowledge_service.create(db, data)
    return success(knowledge_service._to_out(k), message="创建成功")


@router.put("/{kid}")
async def update_knowledge(kid: int, data: KnowledgeUpdate, db: Session = Depends(get_db)):
    """更新知识"""
    k = await knowledge_service.update(db, kid, data)
    return success(knowledge_service._to_out(k), message="更新成功")


@router.delete("/{kid}")
def delete_knowledge(kid: int, db: Session = Depends(get_db)):
    """删除知识"""
    knowledge_service.delete(db, kid)
    return success(message="删除成功")


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    category_id: Optional[int] = Form(None),
    tag_ids: str = Form(""),
    auto_tag: bool = Form(False),
    db: Session = Depends(get_db),
):
    """批量上传文件

    Args:
        category_id: 可选，指定分类
        tag_ids: 逗号分隔的标签 ID 列表
        auto_tag: 是否自动打标签（LLM 分析内容）
    """
    if not files:
        raise APIError("请选择要上传的文件")
    # 解析 tag_ids
    tid_list = []
    if tag_ids:
        tid_list = [int(x.strip()) for x in tag_ids.split(",") if x.strip()]
    result = await knowledge_service.upload_files(
        db, files, category_id=category_id, tag_ids=tid_list, auto_tag=auto_tag
    )
    created = result["created"]
    skipped = result.get("skipped_duplicate", [])
    failed = result.get("failed", [])
    msg = f"成功上传 {len(created)} 个文件"
    if skipped:
        msg += f"，跳过 {len(skipped)} 个重复文件"
    if failed:
        msg += f"，{len(failed)} 个文件失败"
    return success(
        {
            "items": [knowledge_service._to_out(k) for k in created],
            "skipped_duplicate": skipped,
            "failed": failed,
        },
        message=msg,
    )


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


@router.get("/{kid}/status-logs")
def get_status_logs(kid: int, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    """查询指定知识的状态变更审计日志"""
    items, total = knowledge_service.get_status_logs(db, knowledge_id=kid, page=page, page_size=page_size)
    return page_result(items, total, page, page_size)


@router.get("/{kid}/chunks")
def get_chunks(kid: int, db: Session = Depends(get_db)):
    """获取知识的向量分块列表（chunk 级别视图，用于调试和检查检索质量）"""
    from app.services.vector_store import vector_store
    # 先确认知识存在
    knowledge_service.get_by_id(db, kid)
    try:
        # 获取所有分块（最多 500 个）
        raw_chunks = vector_store.get_by_knowledge_id(kid, limit=500)
    except Exception:
        raw_chunks = []
    chunks = []
    for c in raw_chunks:
        meta = c.get("metadata", {}) or {}
        chunks.append({
            "id": c.get("id", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "document": c.get("document", ""),
            "char_count": len(c.get("document", "") or ""),
            "metadata": meta,
        })
    # 按 chunk_index 排序
    chunks.sort(key=lambda x: x.get("chunk_index", 0))
    return success({"chunks": chunks, "total": len(chunks)})


@router.post("/rebuild-indexes")
async def rebuild_indexes(db: Session = Depends(get_db)):
    """重建所有知识的向量索引（切换 Embedding 模型后调用）"""
    result = await knowledge_service.rebuild_all_indexes(db)
    return success(result, message=f"重建完成: 成功 {result['success']}/{result['total']}")


@router.post("/{kid}/rebuild-index")
async def rebuild_single_index(kid: int, db: Session = Depends(get_db)):
    """重建单条知识的向量索引"""
    knowledge_service.get_by_id(db, kid)
    ok = await knowledge_service.sync_vector_index(db, kid)
    return success({"success": ok}, message="索引重建成功" if ok else "索引重建失败（可能未配置 Embedding 或状态非 published）")


@router.post("/{kid}/test-retrieval")
async def test_chunk_retrieval(kid: int, data: dict, db: Session = Depends(get_db)):
    """chunk 检索测试：输入 query，返回该知识内命中的 chunk 及得分

    Body: {query: str, top_k?: int}
    """
    query = (data.get("query") or "").strip()
    if not query:
        raise APIError("query 不能为空", status_code=400)
    top_k = int(data.get("top_k", 5))
    if top_k < 1 or top_k > 50:
        top_k = 5
    knowledge_service.get_by_id(db, kid)
    try:
        from app.services.embedding_service import embedding_service
        from app.services.vector_store import vector_store
        q_vecs = await embedding_service.embed([query], source="test_retrieval")
        if not q_vecs:
            return success({"hits": [], "total": 0}, message="Embedding 服务不可用")
        hits = vector_store.search(
            q_vecs[0],
            where={"knowledge_id": kid},
            top_k=top_k,
        )
        result = [
            {
                "id": h.get("id", ""),
                "chunk_index": (h.get("metadata") or {}).get("chunk_index", 0),
                "score": round(h.get("score", 0.0), 4),
                "document": h.get("document", ""),
            }
            for h in hits
        ]
        return success({"hits": result, "total": len(result)})
    except Exception as e:
        raise APIError(f"检索测试失败: {str(e)}", status_code=500)


@router.get("/{kid}/documents/{doc_id}/download")
def download_document(kid: int, doc_id: int, db: Session = Depends(get_db)):
    """下载知识条目的附件"""
    from app.models import Document
    doc = db.query(Document).filter(Document.id == doc_id, Document.knowledge_id == kid).first()
    if not doc:
        raise APIError("附件不存在", status_code=404)
    file_path = doc.file_path
    if not os.path.isabs(file_path):
        # file_path 可能是 "data\uploads\filename" 或仅 "filename"
        if file_path.startswith("data") or file_path.startswith("uploads"):
            file_path = os.path.join(str(BASE_DIR), file_path)
        else:
            from app.config import UPLOAD_PATH
            file_path = os.path.join(UPLOAD_PATH, file_path)
    if not os.path.exists(file_path):
        raise APIError("文件不存在或已删除", status_code=404)
    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/octet-stream",
    )
