"""PDF 解析后端抽象层

支持多种解析后端，通过配置切换：
- pypdf2: 原有 PyPDF2 文本层抽取（默认，零依赖）
- deepseek-ocr: 硅基流动 DeepSeek-OCR API（直接吃 PDF 返回结构化 Markdown）
- vlm: 多模态 LLM 视觉理解（按页转图后调用 vision API）

设计目标：参照 RAGFlow DeepDOC 能力，以零部署成本补齐解析短板。
"""
import base64
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """统一解析结果"""
    text: str = ""                          # 提取的文本（Markdown 格式）
    pages: list = field(default_factory=list)   # 页级元数据
    tables: list = field(default_factory=list)  # 提取的表格
    images: list = field(default_factory=list)  # 图片信息
    backend: str = ""                       # 使用的后端名称
    page_count: int = 0                     # 总页数


class PDFParserBackend(ABC):
    """PDF 解析后端抽象基类"""

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """解析 PDF 文件，返回结构化结果"""
        pass


class PyPDF2Backend(PDFParserBackend):
    """原有 PyPDF2 实现（兜底，零依赖）"""

    def parse(self, file_path: str) -> ParseResult:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        texts = []
        page_count = 0
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            texts.append(text)
            page_count += 1
        return ParseResult(
            text="\n".join(texts).strip(),
            pages=[],
            tables=[],
            images=[],
            backend="pypdf2",
            page_count=page_count,
        )


class DeepSeekOCRBackend(PDFParserBackend):
    """硅基流动 DeepSeek-OCR 解析后端

    核心优势：
    - 原生支持 PDF 文件直接输入（base64），无需先转图片
    - 输出结构化 Markdown（含表格、标题层级）
    - 零部署成本，仅调用 API
    """

    def __init__(self, api_key: str, base_url: str = "https://api.siliconflow.cn/v1",
                 model: str = "deepseek-ai/DeepSeek-OCR", timeout: int = 300):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def parse(self, file_path: str) -> ParseResult:
        import httpx

        if not self.api_key:
            raise ValueError("DeepSeek-OCR 后端需要 API Key，请在模型配置中添加类型为 'rerank' 或环境变量 DEEPSEEK_OCR_API_KEY")

        # 读取 PDF 并 base64 编码
        file_size = os.path.getsize(file_path)
        if file_size > 20 * 1024 * 1024:  # 20MB 安全上限
            logger.warning(f"[DeepSeek-OCR] 文件较大 ({file_size // 1024 // 1024}MB)，API 可能超时")

        with open(file_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode()

        # DeepSeek-OCR 支持 PDF 直接输入
        prompt = "请将这份 PDF 文档转换为结构化 Markdown：\n1. 保留标题层级（# ## ###）\n2. 表格转为 Markdown 表格\n3. 忽略页眉页脚\n4. 公式用 LaTeX 表示"

        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:application/pdf;base64,{pdf_b64}"}
                    },
                    {"type": "text", "text": prompt}
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[DeepSeek-OCR] API 返回错误 status={e.response.status_code} body={e.response.text[:500]}")
            raise RuntimeError(f"DeepSeek-OCR API 错误: {e.response.status_code}")
        except Exception as e:
            logger.exception(f"[DeepSeek-OCR] 调用失败")
            raise RuntimeError(f"DeepSeek-OCR 调用失败: {type(e).__name__}")

        md_content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        if not md_content.strip():
            logger.warning("[DeepSeek-OCR] 返回空内容，回退到 PyPDF2")
            return PyPDF2Backend().parse(file_path)

        usage = data.get("usage", {})
        logger.info(
            f"[DeepSeek-OCR] 解析成功 chars={len(md_content)} "
            f"tokens(in={usage.get('prompt_tokens', 0)}, out={usage.get('completion_tokens', 0)})"
        )

        return ParseResult(
            text=md_content.strip(),
            pages=[],
            tables=[],
            images=[],
            backend="deepseek-ocr",
            page_count=0,  # DeepSeek-OCR 不返回页码
        )


class VLMBackend(PDFParserBackend):
    """多模态 LLM 视觉解析后端（按页转图后调用 vision API）

    适用于 DeepSeek-OCR 不可用或需要图片语义理解的场景。
    使用 OpenAI 兼容的 vision API（如 Qwen3-VL、GPT-4o）。
    """

    def __init__(self, api_key: str, base_url: str = "https://api.siliconflow.cn/v1",
                 model: str = "Qwen/Qwen3-VL-32B-Instruct", timeout: int = 300,
                 dpi: int = 150, max_pages: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.dpi = dpi
        self.max_pages = max_pages

    def parse(self, file_path: str) -> ParseResult:
        import httpx
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("[VLM] PyMuPDF 未安装，无法按页转图。请 pip install pymupdf")
            return PyPDF2Backend().parse(file_path)

        doc = fitz.open(file_path)
        total_pages = len(doc)
        pages_to_process = min(total_pages, self.max_pages)
        if total_pages > self.max_pages:
            logger.warning(f"[VLM] 文档共 {total_pages} 页，仅处理前 {self.max_pages} 页")

        prompt = "请将这页文档转换为结构化 Markdown：保留标题层级、表格转 Markdown 表格、图片用 [图片: 描述] 占位、忽略页眉页脚。"

        full_text = []
        for page_idx in range(pages_to_process):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=self.dpi)
            img_b64 = base64.b64encode(pix.tobytes("png")).decode()

            payload = {
                "model": self.model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]
                }],
                "temperature": 0.1,
                "max_tokens": 4096,
            }

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                page_md = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                if page_md.strip():
                    full_text.append(f"<!-- page {page_idx + 1} -->\n{page_md}")
            except Exception:
                logger.exception(f"[VLM] 第 {page_idx + 1} 页解析失败")
                # 失败页用 PyPDF2 兜底
                text = page.get_text() or ""
                if text.strip():
                    full_text.append(f"<!-- page {page_idx + 1} (fallback) -->\n{text}")

        doc.close()
        return ParseResult(
            text="\n\n".join(full_text).strip(),
            pages=[],
            tables=[],
            images=[],
            backend="vlm",
            page_count=total_pages,
        )


def get_pdf_backend() -> PDFParserBackend:
    """根据配置获取 PDF 解析后端

    优先级：
    1. 环境变量 PDF_PARSER_BACKEND 指定
    2. 数据库中类型为 'ocr' 的激活模型（运行时动态配置）
    3. 默认 pypdf2
    """
    from app.config import (
        PDF_PARSER_BACKEND,
        DEEPSEEK_OCR_API_KEY,
        DEEPSEEK_OCR_BASE_URL,
        DEEPSEEK_OCR_MODEL,
        VLM_API_KEY,
        VLM_BASE_URL,
        VLM_MODEL,
    )

    backend_name = (PDF_PARSER_BACKEND or "").lower()

    # 优先尝试数据库中的 ocr 类型模型配置（支持运行时热更新）
    if backend_name in ("", "auto"):
        try:
            from app.services.llm_client import model_manager
            ocr_client = model_manager.get_active_ocr()
            if ocr_client:
                return ocr_client.backend
        except Exception:
            pass

    if backend_name in ("deepseek-ocr", "deepseek_ocr"):
        api_key = DEEPSEEK_OCR_API_KEY
        if not api_key:
            logger.warning("[pdf_backend] DeepSeek-OCR 后端未配置 API Key，回退到 PyPDF2")
            return PyPDF2Backend()
        return DeepSeekOCRBackend(
            api_key=api_key,
            base_url=DEEPSEEK_OCR_BASE_URL,
            model=DEEPSEEK_OCR_MODEL,
        )

    if backend_name == "vlm":
        api_key = VLM_API_KEY
        if not api_key:
            logger.warning("[pdf_backend] VLM 后端未配置 API Key，回退到 PyPDF2")
            return PyPDF2Backend()
        return VLMBackend(
            api_key=api_key,
            base_url=VLM_BASE_URL,
            model=VLM_MODEL,
        )

    # 默认 PyPDF2
    return PyPDF2Backend()
