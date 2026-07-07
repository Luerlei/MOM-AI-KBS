"""基础配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/knowledge.db")
VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", str(BASE_DIR / "data" / "vectors"))
UPLOAD_PATH: str = os.getenv("UPLOAD_PATH", str(BASE_DIR / "data" / "uploads"))
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

# 缓存相似度阈值（MOM制造术语变化小，0.90比0.95更合理）
CACHE_SIMILARITY_THRESHOLD: float = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.90"))

# 确保数据目录存在
Path(VECTOR_DB_PATH).mkdir(parents=True, exist_ok=True)
Path(UPLOAD_PATH).mkdir(parents=True, exist_ok=True)
Path(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)

# 允许的文件上传类型
ALLOWED_FILE_TYPES = {
    "pdf": ["application/pdf"],
    "docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    "md": ["text/markdown", "text/plain"],
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 文件扩展名到解析器的映射
FILE_PARSER_MAP = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".md": "markdown",
    ".markdown": "markdown",
}
