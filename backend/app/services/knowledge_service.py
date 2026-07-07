"""知识管理服务"""
import asyncio
import os
from typing import Optional

from app.models import Knowledge, Category, Tag, Document
from app.models.knowledge import knowledge_tags
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, BatchOperation
from app.utils.response import APIError
from app.services.text_chunker import chunk as chunk_text
from app.services.vector_store import vector_store


def _to_out(k: Knowledge) -> dict:
    """转输出格式"""
    return {
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


def get_list(db, page: int = 1, page_size: int = 10, category_id: Optional[int] = None,
             tag_ids: Optional[list] = None, keyword: Optional[str] = None):
    """分页查询，支持筛选"""
    q = db.query(Knowledge)
    if category_id:
        q = q.filter(Knowledge.category_id == category_id)
    if tag_ids:
        q = q.join(knowledge_tags).join(Tag).filter(Tag.id.in_(tag_ids))
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


def create(db, data: KnowledgeCreate) -> Knowledge:
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
        sync_vector_index(db, k.id)
    except APIError:
        # 未配置 Embedding 模型时跳过
        pass
    return k


def update(db, id: int, data: KnowledgeUpdate) -> Knowledge:
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
        sync_vector_index(db, k.id)
    except APIError:
        pass
    return k


def delete(db, id: int):
    """删除知识条目 + 移除向量索引"""
    k = get_by_id(db, id)
    remove_vector_index(k.id)
    db.delete(k)
    db.commit()


def upload_files(db, files: list):
    """批量上传文件，解析，创建知识条目，生成向量索引

    Args:
        files: FastAPI UploadFile 列表
    """
    from app.services.file_parser import save_upload_file, parse_file, get_file_type

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
            content_type="标准文档",
            source_type="upload",
            source_file=filename,
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
        # 同步向量索引
        try:
            sync_vector_index(db, k.id)
        except APIError:
            pass
        created.append(k)
    return created


def batch_operation(db, data: BatchOperation):
    """批量操作：delete / add_tag(s) / move_category / set_category"""
    if not data.ids:
        raise APIError("请选择要操作的条目")
    if data.action == "delete":
        for kid in data.ids:
            try:
                remove_vector_index(kid)
            except Exception:
                pass
        db.query(Knowledge).filter(Knowledge.id.in_(data.ids)).delete(synchronize_session=False)
        db.commit()
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


def sync_vector_index(db, knowledge_id: int):
    """同步向量索引：分块 -> Embedding -> ChromaDB.add

    MVP 阶段同步调用；embedding 为 async，此处用专用事件循环执行。
    """
    k = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not k:
        return
    if not k.content or not k.content.strip():
        return
    # 先移除旧的
    remove_vector_index(knowledge_id)
    # 分块
    chunks = chunk_text(k.content, chunk_size=500, overlap=50)
    if not chunks:
        return
    # 向量化（在新事件循环中执行 async embed）
    from app.services.embedding_service import embedding_service
    embeddings = _run_async(embedding_service.embed(chunks, source="sync_index"))
    if not embeddings or len(embeddings) != len(chunks):
        return
    # metadata
    metadata = []
    for i, c in enumerate(chunks):
        metadata.append({
            "knowledge_id": knowledge_id,
            "title": k.title,
            "category_id": str(k.category_id) if k.category_id else "",
            "chunk_index": i,
        })
    vector_store.add(
        knowledge_id=knowledge_id,
        chunks=chunks,
        embeddings=embeddings,
        metadata=metadata,
    )


def _run_async(coro):
    """在同步上下文中执行 coroutine，兼容已有事件循环和线程池场景"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已在事件循环中（如 FastAPI 异步上下文），需新建独立循环执行
            import threading
            result = {}
            error = {}

            def _run():
                new_loop = asyncio.new_event_loop()
                try:
                    result["value"] = new_loop.run_until_complete(coro)
                except Exception as e:
                    error["exc"] = e
                finally:
                    new_loop.close()

            t = threading.Thread(target=_run)
            t.start()
            t.join()
            if "exc" in error:
                raise error["exc"]
            return result.get("value")
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # 没有事件循环（如 worker 线程），新建一个
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def remove_vector_index(knowledge_id: int):
    """移除向量索引"""
    try:
        vector_store.delete(knowledge_id)
    except Exception:
        pass


def rebuild_all_indexes(db):
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
            embeddings = _run_async(embedding_service.embed(chunks, source="sync_index"))
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
            failed += 1
    return {"total": total, "success": success, "failed": failed, "skipped": skipped}
