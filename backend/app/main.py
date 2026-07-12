"""FastAPI应用入口"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import DEBUG, get_cors_origins, validate_security_config
from app.database import init_db
from app.utils.response import success, error, APIError

logger = logging.getLogger(__name__)

# 速率限制器（按客户端 IP 限流）
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时安全校验
    validate_security_config()
    init_db()
    # 初始化预制数据
    from app.services.seed_service import seed_initial_data
    seed_initial_data()
    print("=" * 50)
    print("  MOM AI知识库平台 已启动")
    print("  API文档: http://localhost:8000/docs")
    print("=" * 50)
    yield


app = FastAPI(
    title="MOM系统AI知识库平台",
    description="Skill路由 + 自实现轻量RAG 架构的制造企业知识库平台",
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan,
)

# 注册速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS：从环境变量 CORS_ORIGINS 读取（逗号分隔），开发环境默认 *，
# 生产环境应明确指定来源（如 http://localhost:5173,https://your.domain）
_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # 注意：allow_origins=["*"] 时 allow_credentials 不能为 True（浏览器会拒绝）
    # 仅在指定具体来源时才允许 credentials
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error(exc.message, exc.code),
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    # 详情只进日志，不返回给客户端（避免泄露栈/路径/SQL 等敏感信息）
    logger.exception(f"[unhandled] {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content=error("服务器内部错误", status_code=500),
    )


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点

    使用 `with SessionLocal() as db:` 保证异常分支也会关闭 session。
    """
    import sqlalchemy
    from app.database import SessionLocal
    from app.models import ModelConfig
    from app.config import VECTOR_DB_PATH

    # 数据库状态
    try:
        with SessionLocal() as db:
            db.execute(sqlalchemy.text("SELECT 1"))
            llm_count = db.query(ModelConfig).filter(ModelConfig.type == "LLM").count()
            embedding_count = db.query(ModelConfig).filter(ModelConfig.type == "Embedding").count()
            forecast_count = db.query(ModelConfig).filter(ModelConfig.type == "Forecast").count()
        db_status = "ok"
        model_status = {
            "llm_configs": llm_count,
            "embedding_configs": embedding_count,
            "forecast_configs": forecast_count,
        }
    except Exception as e:
        db_status = f"error: {e}"
        model_status = "error"

    # 向量库状态
    vector_status = "ok" if os.path.exists(VECTOR_DB_PATH) else "not_initialized"

    return success({
        "status": "healthy",
        "database": db_status,
        "vector_db": vector_status,
        "models": model_status,
    })


# 根路径
@app.get("/")
async def root():
    return success({"name": "MOM系统AI知识库平台", "version": "1.0.0"})


# 注册路由
from app.routers import knowledge, category, tag, skill, skill_option, model_config, search, qa, dashboard, token_stats, dataset, forecast, covariate, auth  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识管理"])
app.include_router(category.router, prefix="/api/categories", tags=["分类管理"])
app.include_router(tag.router, prefix="/api/tags", tags=["标签管理"])
app.include_router(skill.router, prefix="/api/skills", tags=["Skill管理"])
app.include_router(skill_option.router, prefix="/api/skill-options", tags=["Skill选项"])
app.include_router(model_config.router, prefix="/api/models", tags=["模型配置"])
app.include_router(search.router, prefix="/api/search", tags=["搜索"])
app.include_router(qa.router, prefix="/api/qa", tags=["智能问答"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["首页"])
app.include_router(token_stats.router, prefix="/api/token-stats", tags=["Token统计"])
app.include_router(dataset.router, prefix="/api/datasets", tags=["数据集管理"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["时序预测"])
app.include_router(covariate.router, prefix="/api", tags=["协变量管理"])
