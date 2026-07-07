"""FastAPI应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import DEBUG
from app.database import init_db
from app.utils.response import success, error, APIError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    return JSONResponse(
        status_code=500,
        content=error(f"服务器内部错误: {str(exc)}", status_code=500),
    )


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    from app.database import SessionLocal
    from app.models import ModelConfig
    from app.config import VECTOR_DB_PATH
    import os

    db = SessionLocal()
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    finally:
        db.close()

    # 向量库状态
    vector_status = "ok" if os.path.exists(VECTOR_DB_PATH) else "not_initialized"

    # 模型配置状态
    try:
        db = SessionLocal()
        llm_count = db.query(ModelConfig).filter(ModelConfig.type == "LLM").count()
        embedding_count = db.query(ModelConfig).filter(ModelConfig.type == "Embedding").count()
        model_status = {"llm_configs": llm_count, "embedding_configs": embedding_count}
        db.close()
    except Exception:
        model_status = "error"

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
from app.routers import knowledge, category, tag, skill, skill_option, model_config, search, qa, dashboard, token_stats  # noqa: E402

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
