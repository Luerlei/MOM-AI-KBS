"""文件解析服务，支持 PDF / Word / Excel / Markdown"""
import os
from pathlib import Path
from typing import Optional

from app.config import UPLOAD_PATH, FILE_PARSER_MAP, ALLOWED_FILE_TYPES, MAX_FILE_SIZE
from app.utils.response import APIError


def get_file_type(filename: str) -> str:
    """从文件名获取类型（扩展名，不带点），未知返回空字符串"""
    ext = Path(filename).suffix.lower()
    return FILE_PARSER_MAP.get(ext, "")


def parse_file(file_path: str, file_type: str) -> str:
    """解析文件，返回提取的纯文本内容

    Args:
        file_path: 文件绝对路径
        file_type: 文件类型(pdf/docx/xlsx/markdown)
    """
    if not os.path.exists(file_path):
        raise APIError(f"文件不存在: {file_path}", status_code=404)

    try:
        if file_type == "pdf":
            return _parse_pdf(file_path)
        if file_type == "docx":
            return _parse_docx(file_path)
        if file_type == "xlsx":
            return _parse_xlsx(file_path)
        if file_type in ("markdown", "md"):
            return _parse_markdown(file_path)
        raise APIError(f"不支持的文件类型: {file_type}")
    except APIError:
        raise
    except Exception as e:
        raise APIError(f"文件解析失败: {str(e)}")


def _parse_pdf(file_path: str) -> str:
    """解析PDF文件"""
    from PyPDF2 import PdfReader
    reader = PdfReader(file_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        texts.append(text)
    return "\n".join(texts).strip()


def _parse_docx(file_path: str) -> str:
    """解析Word docx文件"""
    from docx import Document
    doc = Document(file_path)
    texts = []
    for para in doc.paragraphs:
        if para.text:
            texts.append(para.text)
    # 表格内容
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                texts.append(" | ".join(cells))
    return "\n".join(texts).strip()


def _parse_xlsx(file_path: str) -> str:
    """解析Excel xlsx文件"""
    from openpyxl import load_workbook
    wb = load_workbook(file_path, data_only=True, read_only=True)
    texts = []
    for sheet in wb.worksheets:
        texts.append(f"# {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                texts.append(" | ".join(cells))
    wb.close()
    return "\n".join(texts).strip()


def _parse_markdown(file_path: str) -> str:
    """读取Markdown文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_upload_file(upload_file, filename: str) -> str:
    """保存上传文件到 UPLOAD_PATH，返回存储路径

    Args:
        upload_file: FastAPI UploadFile 对象
        filename: 目标文件名
    """
    file_type = get_file_type(filename)
    if not file_type:
        raise APIError(f"不支持的文件类型，允许: {', '.join(FILE_PARSER_MAP.keys())}")

    # 防止文件名冲突：加时间戳前缀
    import time
    safe_name = f"{int(time.time())}_{filename}"
    target_dir = Path(UPLOAD_PATH)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name

    # 写入文件
    contents = upload_file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise APIError(f"文件大小超过限制({MAX_FILE_SIZE // 1024 // 1024}MB)")
    with open(target_path, "wb") as f:
        f.write(contents)

    return str(target_path)
