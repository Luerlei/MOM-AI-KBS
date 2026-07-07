"""数据库连接和会话管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库（建表）"""
    from app.models import knowledge, category, tag, document, skill, model_config, qa_history, token_usage, search_history  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _auto_migrate()


def _auto_migrate():
    """轻量级自动迁移：为已存在的表补充新增列（SQLite ALTER TABLE ADD COLUMN）"""
    import sqlite3
    from app.config import DATABASE_URL
    db_path = DATABASE_URL.replace("sqlite:///", "")
    # 要补充的列：表名 -> [(列名, 列定义SQL)]
    migrations = {
        "token_usage": [
            ("source", "VARCHAR(50) DEFAULT 'qa'"),
        ],
    }
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for table, cols in migrations.items():
            cur.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cur.fetchall()}
            for col_name, col_def in cols:
                if col_name not in existing:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    conn.commit()
        conn.close()
    except Exception:
        pass
