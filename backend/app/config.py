"""基础配置"""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/knowledge.db")
VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", str(BASE_DIR / "data" / "vectors"))
UPLOAD_PATH: str = os.getenv("UPLOAD_PATH", str(BASE_DIR / "data" / "uploads"))
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# 认证配置：AUTH_ENABLED=true 时启用 JWT 认证，保护敏感 API
AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "changeme")
JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# CORS 允许的来源（逗号分隔，* 表示全部；生产环境应明确指定来源）
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

# 缓存相似度阈值（MOM制造术语变化小，0.90比0.95更合理）
CACHE_SIMILARITY_THRESHOLD: float = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.90"))

# 缓存过期时间（秒），默认 7 天
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", str(7 * 24 * 3600)))

# RAG 检索相似度阈值：低于此分数的 chunk 不纳入上下文
RAG_RELEVANCE_THRESHOLD: float = float(os.getenv("RAG_RELEVANCE_THRESHOLD", "0.3"))

# 速率限制配置（每分钟请求数）
RATE_LIMIT_QA: str = os.getenv("RATE_LIMIT_QA", "30/minute")        # 问答（含流式）
RATE_LIMIT_SEARCH: str = os.getenv("RATE_LIMIT_SEARCH", "60/minute")  # 搜索（较轻）
RATE_LIMIT_FORECAST: str = os.getenv("RATE_LIMIT_FORECAST", "10/minute")  # 预测（重负载）
RATE_LIMIT_SUGGESTIONS: str = os.getenv("RATE_LIMIT_SUGGESTIONS", "60/minute")  # 追问推荐

# 查询改写缓存配置
QUERY_REWRITE_CACHE_TTL: int = int(os.getenv("QUERY_REWRITE_CACHE_TTL", str(30 * 60)))  # 30 分钟
QUERY_REWRITE_CACHE_MAXSIZE: int = int(os.getenv("QUERY_REWRITE_CACHE_MAXSIZE", "500"))

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
    "txt": ["text/plain"],
    "html": ["text/html"],
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 文件扩展名到解析器的映射
FILE_PARSER_MAP = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".text": "text",
    ".html": "html",
    ".htm": "html",
}


def get_cors_origins() -> list:
    """解析 CORS_ORIGINS 为列表"""
    if CORS_ORIGINS.strip() == "*":
        return ["*"]
    return [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]


def validate_security_config():
    """启动时校验安全配置：生产环境（DEBUG=false）下校验关键安全项"""
    if not DEBUG:
        # SECRET_KEY
        if SECRET_KEY == "dev-secret-key-change-in-production":
            raise RuntimeError(
                "生产环境（DEBUG=false）必须设置 SECRET_KEY 环境变量，不能使用默认值。"
                "请设置 SECRET_KEY=<随机字符串> 后再启动。"
            )
        if SECRET_KEY and len(SECRET_KEY) < 16:
            logger.warning("[security] SECRET_KEY 长度不足 16，建议使用更长的随机字符串。")
        # S2: ADMIN_PASSWORD 不能是默认值
        if ADMIN_PASSWORD == "changeme":
            raise RuntimeError(
                "生产环境（DEBUG=false）必须设置 ADMIN_PASSWORD 环境变量，不能使用默认值 changeme。"
            )
        if len(ADMIN_PASSWORD) < 8:
            logger.warning("[security] ADMIN_PASSWORD 长度不足 8，建议使用更强的密码。")
        # S4: CORS_ORIGINS 不能为 *
        if CORS_ORIGINS.strip() == "*":
            raise RuntimeError(
                "生产环境（DEBUG=false）不允许 CORS_ORIGINS=*，请明确指定允许的前端来源（逗号分隔）。"
            )
        # B-P1-1: 生产环境必须开启认证
        if not AUTH_ENABLED:
            raise RuntimeError(
                "生产环境（DEBUG=false）必须开启认证：设置 AUTH_ENABLED=true 后再启动。"
            )
