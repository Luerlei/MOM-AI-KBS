"""知识管理服务"""
import logging
import os
from typing import Optional

from app.models import Knowledge, Category, Tag, Document
from app.models.knowledge import knowledge_tags
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, BatchOperation
from app.utils.response import APIError
from app.services.text_chunker import chunk as chunk_text
from app.services.vector_store import vector_store
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def _clear_answer_cache():
    """清除答案缓存（知识更新/删除后调用，防止返回过期内容）"""
    try:
        from app.services.cache_service import answer_cache
        answer_cache.clear()
    except Exception:
        logger.exception("[knowledge] 清除答案缓存失败")


def _to_out(k: Knowledge, include_index_status: bool = False) -> dict:
    """转输出格式"""
    out = {
        "id": k.id,
        "title": k.title,
        "content": k.content,
        "content_type": k.content_type,
        "category_id": k.category_id,
        "category_name": k.category.name if k.category else None,
        "source_type": k.source_type,
        "source_file": k.source_file,
        "tag_ids": [t.id for t in k.tags],
        "tag_names": [t.name for t in k.tags],
        "tags": [{"id": t.id, "name": t.name} for t in k.tags],
        "created_at": k.created_at,
        "updated_at": k.updated_at,
    }
    if include_index_status:
        # 仅在详情页查询向量索引状态（避免列表页 N+1）
        try:
            chunks = vector_store.get_by_knowledge_id(k.id, limit=1)
            out["vector_indexed"] = len(chunks) > 0
        except Exception:
            out["vector_indexed"] = False
    return out


def get_list(db, page: int = 1, page_size: int = 10, category_id: Optional[int] = None,
             tag_ids: Optional[list] = None, keyword: Optional[str] = None):
    """分页查询，支持筛选"""
    q = db.query(Knowledge).options(joinedload(Knowledge.category), joinedload(Knowledge.tags))
    if category_id:
        q = q.filter(Knowledge.category_id == category_id)
    if tag_ids:
        q = q.join(knowledge_tags).join(Tag).filter(Tag.id.in_(tag_ids)).distinct()
    if keyword:
        q = q.filter(Knowledge.title.like(f"%{keyword}%") | Knowledge.content.like(f"%{keyword}%"))
    total = q.count()
    items = q.order_by(Knowledge.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_to_out(k) for k in items], total


def get_by_id(db, id: int) -> Knowledge:
    k = db.query(Knowledge).filter(Knowledge.id == id).first()
    if not k:
        raise APIError("知识条目不存在", status_code=404)
    return k


async def create(db, data: KnowledgeCreate) -> Knowledge:
    """创建知识条目 + 同步向量索引"""
    k = Knowledge(
        title=data.title,
        content=data.content,
        content_type=data.content_type,
        category_id=data.category_id,
        source_type="manual",
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    # 关联标签
    if data.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        k.tags = tags
        db.commit()
        db.refresh(k)
    # 同步向量索引
    try:
        await sync_vector_index(db, k.id)
    except APIError:
        # 未配置 Embedding 模型时跳过
        pass
    except Exception:
        logger.exception(f"[create] 同步向量索引失败 knowledge_id={k.id}")
    return k


async def update(db, id: int, data: KnowledgeUpdate) -> Knowledge:
    """更新知识条目 + 重建向量索引"""
    k = get_by_id(db, id)
    if data.title is not None:
        k.title = data.title
    if data.content is not None:
        k.content = data.content
    if data.content_type is not None:
        k.content_type = data.content_type
    if data.category_id is not None:
        k.category_id = data.category_id
    if data.tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        k.tags = tags
    db.commit()
    db.refresh(k)
    # 重建向量索引
    try:
        await sync_vector_index(db, k.id)
    except APIError:
        pass
    except Exception:
        logger.exception(f"[update] 同步向量索引失败 knowledge_id={k.id}")
    # 知识更新后清除答案缓存，防止返回过期内容
    _clear_answer_cache()
    return k


def delete(db, id: int):
    """删除知识条目 + 移除向量索引"""
    k = get_by_id(db, id)
    remove_vector_index(k.id)
    db.delete(k)
    db.commit()
    # 知识删除后清除答案缓存，防止返回过期内容
    _clear_answer_cache()


async def upload_files(db, files: list, category_id: int = None, tag_ids: list = None, auto_tag: bool = False):
    """批量上传文件，解析，创建知识条目，生成向量索引

    Args:
        files: FastAPI UploadFile 列表
        category_id: 可选，指定分类
        tag_ids: 可选，预置标签 ID 列表
        auto_tag: 是否自动打标签（LLM 分析内容，1-3 个标签）
    """
    from app.services.file_parser import save_upload_file, parse_file, get_file_type

    # 预加载现有标签
    existing_tags = db.query(Tag).all() if (tag_ids or auto_tag) else []
    tag_id_set = set(tag_ids or [])

    created = []
    for upload_file in files:
        filename = upload_file.filename or "unknown.txt"
        file_type = get_file_type(filename)
        if not file_type:
            continue
        # 保存
        file_path = save_upload_file(upload_file, filename)
        # 解析
        content = parse_file(file_path, file_type)
        # 创建知识条目
        k = Knowledge(
            title=os.path.splitext(filename)[0],
            content=content,
            content_type="markdown",
            source_type="upload",
            source_file=filename,
            category_id=category_id,
        )
        db.add(k)
        db.commit()
        db.refresh(k)
        # 记录文档
        doc = Document(
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            knowledge_id=k.id,
        )
        db.add(doc)
        db.commit()
        db.refresh(k)
        # 预置标签
        if tag_id_set:
            for t in existing_tags:
                if t.id in tag_id_set:
                    k.tags.append(t)
            db.commit()
            db.refresh(k)
        # 自动打标签
        if auto_tag:
            try:
                assigned = await _auto_tag_knowledge(db, k, content, existing_tags)
                if assigned:
                    db.refresh(k)
                    # 更新本地缓存
                    for t in assigned:
                        if t not in existing_tags:
                            existing_tags.append(t)
                    logger.info(f"[upload_files] auto_tag knowledge_id={k.id} tags={[t.name for t in assigned]}")
            except Exception:
                logger.exception(f"[upload_files] auto_tag 失败 knowledge_id={k.id}")
        # 同步向量索引
        try:
            await sync_vector_index(db, k.id)
        except APIError:
            pass
        except Exception:
            logger.exception(f"[upload_files] 同步向量索引失败 knowledge_id={k.id}")
        created.append(k)
    return created


async def _auto_tag_knowledge(db, knowledge, content: str, existing_tags: list):
    """LLM 分析内容自动打标签

    策略：先匹配现有标签，不够再新建。最少 1 个，最多 3 个。

    Returns:
        list[Tag]: 分配的标签列表
    """
    import json
    from app.services.llm_client import ModelManager

    # 截取前 2000 字避免 token 过多
    text_preview = content[:2000] if content else ""
    if not text_preview.strip():
        return []

    tag_names = [t.name for t in existing_tags]
    prompt = f"""请分析以下文档内容，为其推荐 1-3 个标签。

现有标签列表：{json.dumps(tag_names, ensure_ascii=False) if tag_names else "[]"}

文档内容（前2000字）：
{text_preview}

要求：
1. 优先从现有标签列表中选择匹配的标签
2. 如果现有标签不合适，可以新建标签（简短，2-6个字）
3. 标签总数 1-3 个
4. 只返回标签名称，用逗号分隔，不要有其他内容

示例输出：设备维护, 故障诊断, 保养

标签："""

    try:
        client = ModelManager.get_active_llm()
    except Exception:
        logger.warning("[auto_tag] 未配置 LLM，跳过自动标签")
        return []

    try:
        result = await client.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.3, max_tokens=100)
        raw = result.get("content", "").strip()
    except Exception:
        logger.exception("[auto_tag] LLM 调用失败")
        return []

    # 解析 LLM 返回的标签名
    names = [n.strip() for n in raw.replace("，", ",").replace("、", ",").split(",") if n.strip()]
    # 去重，最多 3 个
    seen = set()
    unique_names = []
    for n in names:
        if n not in seen and len(n) <= 20:
            seen.add(n)
            unique_names.append(n)
    unique_names = unique_names[:3]
    if not unique_names:
        return []

    assigned = []
    for name in unique_names:
        # 先匹配现有标签
        tag = None
        for t in existing_tags:
            if t.name == name:
                tag = t
                break
        # 不存在则新建
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
            existing_tags.append(tag)
        # 关联到知识条目（避免重复）
        if tag not in knowledge.tags:
            knowledge.tags.append(tag)
        assigned.append(tag)
    db.commit()
    return assigned


def batch_operation(db, data: BatchOperation):
    """批量操作：delete / add_tag(s) / move_category / set_category"""
    if not data.ids:
        raise APIError("请选择要操作的条目")
    if data.action == "delete":
        for kid in data.ids:
            try:
                remove_vector_index(kid)
            except Exception:
                logger.exception(f"[batch_operation] 移除向量索引失败 knowledge_id={kid}")
        db.query(Knowledge).filter(Knowledge.id.in_(data.ids)).delete(synchronize_session=False)
        db.commit()
        # 批量删除后清除答案缓存
        _clear_answer_cache()
    elif data.action in ("add_tag", "add_tags"):
        if not data.tag_ids:
            raise APIError("请选择要添加的标签")
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        items = db.query(Knowledge).filter(Knowledge.id.in_(data.ids)).all()
        for k in items:
            existing = set(t.id for t in k.tags)
            for t in tags:
                if t.id not in existing:
                    k.tags.append(t)
        db.commit()
    elif data.action in ("move_category", "set_category"):
        items = db.query(Knowledge).filter(Knowledge.id.in_(data.ids)).all()
        for k in items:
            k.category_id = data.category_id
        db.commit()
    else:
        raise APIError(f"不支持的操作类型: {data.action}")


def get_related(db, knowledge_id: int, limit: int = 5):
    """获取相关内容（同分类或同标签）"""
    k = get_by_id(db, knowledge_id)
    q = db.query(Knowledge).filter(Knowledge.id != knowledge_id)
    same_cat = []
    same_tag = []
    if k.category_id:
        same_cat = q.filter(Knowledge.category_id == k.category_id).limit(limit).all()
    tag_ids = [t.id for t in k.tags]
    if tag_ids:
        same_tag = q.join(knowledge_tags).filter(knowledge_tags.c.tag_id.in_(tag_ids)).limit(limit).all()
    # 合并去重
    seen = set()
    out = []
    for item in same_cat + same_tag:
        if item.id not in seen:
            seen.add(item.id)
            out.append(item)
        if len(out) >= limit:
            break
    return [_to_out(item) for item in out]


async def sync_vector_index(db, knowledge_id: int) -> bool:
    """同步向量索引：分块 -> Embedding -> ChromaDB.add

    返回 True 表示索引成功，False 表示失败或跳过。
    """
    k = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not k:
        return False
    if not k.content or not k.content.strip():
        return False
    # 先移除旧的
    remove_vector_index(knowledge_id)
    # 分块
    chunks = chunk_text(k.content, chunk_size=500, overlap=50)
    if not chunks:
        return False
    # 向量化（直接 await，无需 _run_async）
    from app.services.embedding_service import embedding_service
    try:
        embeddings = await embedding_service.embed(chunks, source="sync_index")
    except Exception:
        logger.exception(f"[sync_vector_index] Embedding 失败 knowledge_id={knowledge_id}")
        return False
    if not embeddings or len(embeddings) != len(chunks):
        return False
    # metadata
    metadata = []
    for i, c in enumerate(chunks):
        metadata.append({
            "knowledge_id": knowledge_id,
            "title": k.title,
            "category_id": str(k.category_id) if k.category_id else "",
            "chunk_index": i,
        })
    try:
        vector_store.add(
            knowledge_id=knowledge_id,
            chunks=chunks,
            embeddings=embeddings,
            metadata=metadata,
        )
        return True
    except Exception:
        logger.exception(f"[sync_vector_index] 写入 ChromaDB 失败 knowledge_id={knowledge_id}")
        return False


def remove_vector_index(knowledge_id: int):
    """移除向量索引"""
    try:
        vector_store.delete(knowledge_id)
    except Exception:
        logger.exception(f"[remove_vector_index] 移除向量索引失败 knowledge_id={knowledge_id}")


async def rebuild_all_indexes(db):
    """重建所有知识的向量索引（用于切换 Embedding 模型后）

    Returns:
        dict: {total, success, failed, skipped}
    """
    items = db.query(Knowledge).all()
    total = len(items)
    success = 0
    failed = 0
    skipped = 0
    for k in items:
        try:
            if not k.content or not k.content.strip():
                skipped += 1
                continue
            # 先清空所有旧索引（避免维度混乱）
            remove_vector_index(k.id)
            # 重新生成
            chunks = chunk_text(k.content, chunk_size=500, overlap=50)
            if not chunks:
                skipped += 1
                continue
            from app.services.embedding_service import embedding_service
            embeddings = await embedding_service.embed(chunks, source="sync_index")
            if not embeddings or len(embeddings) != len(chunks):
                failed += 1
                continue
            metadata = []
            for i, c in enumerate(chunks):
                metadata.append({
                    "knowledge_id": k.id,
                    "title": k.title,
                    "category_id": str(k.category_id) if k.category_id else "",
                    "chunk_index": i,
                })
            vector_store.add(
                knowledge_id=k.id,
                chunks=chunks,
                embeddings=embeddings,
                metadata=metadata,
            )
            success += 1
        except Exception:
            logger.exception(f"[rebuild_all_indexes] 重建失败 knowledge_id={k.id}")
            failed += 1
    return {"total": total, "success": success, "failed": failed, "skipped": skipped}
