"""知识库管理路由"""
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services import knowledge_base_service, knowledge_service
from app.utils.auth import require_auth
from app.utils.response import success, APIError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
def list_knowledge_bases(
    keyword: str = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """知识库列表"""
    items, total = knowledge_base_service.get_list(db, keyword=keyword, page=page, page_size=page_size)
    return success({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{kb_id}")
def get_knowledge_base(kb_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """知识库详情"""
    return success(knowledge_base_service.get_detail(db, kb_id))


@router.post("")
def create_knowledge_base(data: KnowledgeBaseCreate, db: Session = Depends(get_db), user=Depends(require_auth)):
    """创建知识库"""
    kb = knowledge_base_service.create(db, data)
    return success(knowledge_base_service.get_detail(db, kb.id), message="创建成功")


@router.put("/{kb_id}")
def update_knowledge_base(kb_id: int, data: KnowledgeBaseUpdate, db: Session = Depends(get_db), user=Depends(require_auth)):
    """更新知识库"""
    kb = knowledge_base_service.update(db, kb_id, data)
    return success(knowledge_base_service.get_detail(db, kb.id), message="更新成功")


@router.delete("/{kb_id}")
def delete_knowledge_base(kb_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """删除知识库（关联资料解除归属，不删除）"""
    knowledge_base_service.delete(db, kb_id)
    return success(message="删除成功")


@router.get("/{kb_id}/documents")
def list_documents(
    kb_id: int,
    page: int = 1,
    page_size: int = 20,
    parse_status: str = None,
    keyword: str = None,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """知识库下的资料列表"""
    from app.models import Knowledge
    q = db.query(Knowledge).filter(Knowledge.knowledge_base_id == kb_id)
    if parse_status:
        q = q.filter(Knowledge.parse_status == parse_status)
    if keyword:
        q = q.filter(Knowledge.title.like(f"%{keyword}%"))
    total = q.count()
    items = q.order_by(Knowledge.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # 复用 knowledge_service 的转输出
    from app.services.knowledge_service import _to_out
    return success({
        "items": [_to_out(k) for k in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/{kb_id}/upload")
async def upload_to_knowledge_base(
    kb_id: int,
    files: list[UploadFile] = File(...),
    category_id: int = Form(None),
    tag_ids: str = Form(""),  # 逗号分隔的标签 ID
    auto_tag: bool = Form(False),
    parse_immediately: bool = Form(None),  # None 表示用知识库的 parse_on_upload 默认值
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """上传资料到知识库（支持多文件 + 文件夹）

    Args:
        parse_immediately: 是否立即解析。None=用知识库默认配置，True=立即解析，False=仅上传
    """
    # 校验知识库存在
    kb = knowledge_base_service.get_by_id(db, kb_id)
    # 确定是否立即解析
    if parse_immediately is None:
        parse_immediately = kb.parse_on_upload
    # 解析 tag_ids
    tag_id_list = []
    if tag_ids:
        try:
            tag_id_list = [int(x.strip()) for x in tag_ids.split(",") if x.strip()]
        except ValueError:
            return APIError("tag_ids 格式错误，应为逗号分隔的数字", status_code=400)
    # 调用上传服务
    result = await knowledge_service.upload_files_to_kb(
        db,
        files=files,
        knowledge_base_id=kb_id,
        category_id=category_id,
        tag_ids=tag_id_list,
        auto_tag=auto_tag,
        parse_immediately=parse_immediately,
    )
    return success({
        "created": len(result.get("created", [])),
        "skipped_duplicate": result.get("skipped_duplicate", []),
        "failed": result.get("failed", []),
    }, message=f"上传完成: 成功 {len(result.get('created', []))} 个, 跳过 {len(result.get('skipped_duplicate', []))} 个, 失败 {len(result.get('failed', []))} 个")


@router.post("/{kb_id}/documents/{kid}/parse")
async def parse_document(kb_id: int, kid: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """手动触发单个资料的解析"""
    from app.models import Knowledge
    k = db.query(Knowledge).filter(Knowledge.id == kid, Knowledge.knowledge_base_id == kb_id).first()
    if not k:
        raise APIError("资料不存在", status_code=404)
    if k.parse_status == "parsing":
        raise APIError("资料正在解析中，请勿重复触发", status_code=400)
    # 执行解析
    await knowledge_service.parse_single_document(db, kid)
    return success(message="解析完成")


@router.post("/{kb_id}/parse-all")
async def parse_all_documents(kb_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    """批量解析知识库下所有待解析的资料"""
    from app.models import Knowledge
    items = db.query(Knowledge).filter(
        Knowledge.knowledge_base_id == kb_id,
        Knowledge.parse_status.in_(["pending", "failed"]),
    ).all()
    success_count = 0
    failed_count = 0
    for k in items:
        try:
            await knowledge_service.parse_single_document(db, k.id)
            success_count += 1
        except Exception:
            failed_count += 1
            logger.exception(f"[parse_all] 解析失败 knowledge_id={k.id}")
    return success({
        "total": len(items),
        "success": success_count,
        "failed": failed_count,
    }, message=f"批量解析完成: 成功 {success_count}, 失败 {failed_count}")
