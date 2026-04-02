"""数据库初始化 —— SQLAlchemy async，支持 SQLite（开发）和 PostgreSQL（生产）

配置方式（环境变量优先级从高到低）：
  HIVE_DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname   # PostgreSQL
  HIVE_DATABASE_URL=sqlite+aiosqlite:////path/to/hive.db          # SQLite（绝对路径）
  HIVE_DB_PATH=/path/to/hive.db                                   # SQLite 简写
  （缺省）data/hive.db                                             # SQLite 本地相对路径

PostgreSQL 连接池参数（仅 PostgreSQL 生效）：
  HIVE_DB_POOL_SIZE=5       # 常驻连接数（默认 5）
  HIVE_DB_MAX_OVERFLOW=10   # 超出 pool_size 的额外连接上限（默认 10）
  HIVE_DB_POOL_TIMEOUT=30   # 等待连接超时秒数（默认 30）
  HIVE_DB_POOL_RECYCLE=1800 # 连接最长存活秒数（默认 1800）
"""

import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


def _build_database_url() -> str:
    """构造数据库 URL，按优先级读取配置"""
    explicit = os.environ.get("HIVE_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    db_path = os.environ.get("HIVE_DB_PATH", "data/hive.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


def _is_postgres(url: str) -> bool:
    return "postgresql" in url or "postgres" in url


def _build_engine_kwargs(url: str) -> dict:
    """根据数据库类型返回合适的引擎参数"""
    kwargs: dict = {
        "echo": os.environ.get("HIVE_DB_ECHO", "0") == "1",
    }
    if _is_postgres(url):
        kwargs.update({
            "pool_size":     int(os.environ.get("HIVE_DB_POOL_SIZE",    "5")),
            "max_overflow":  int(os.environ.get("HIVE_DB_MAX_OVERFLOW", "10")),
            "pool_timeout":  int(os.environ.get("HIVE_DB_POOL_TIMEOUT", "30")),
            "pool_recycle":  int(os.environ.get("HIVE_DB_POOL_RECYCLE", "1800")),
            "pool_pre_ping": True,   # 连接前探活，避免僵尸连接
        })
    else:
        # SQLite：asyncio 模式下必须关闭跨线程检查
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


DATABASE_URL = _build_database_url()

engine = create_async_engine(DATABASE_URL, **_build_engine_kwargs(DATABASE_URL))

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """创建所有表（若不存在）。生产 PostgreSQL 建议改用 Alembic 管理 DDL。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_bootstrap_compat_schema)


async def get_db() -> AsyncSession:
    """FastAPI Depends 注入"""
    async with SessionLocal() as session:
        yield session


def _bootstrap_compat_schema(sync_conn) -> None:
    """Apply lightweight additive changes for existing local databases."""
    inspector = inspect(sync_conn)
    if "tasks" not in inspector.get_table_names():
        return

    existing_columns = {item["name"] for item in inspector.get_columns("tasks")}
    statements: list[str] = []
    if "current_owner_lifeform_id" not in existing_columns:
        statements.append("ALTER TABLE tasks ADD COLUMN current_owner_lifeform_id VARCHAR(64)")
    if "entry_lifeform_id" not in existing_columns:
        statements.append("ALTER TABLE tasks ADD COLUMN entry_lifeform_id VARCHAR(64)")
    if "last_handoff_id" not in existing_columns:
        statements.append("ALTER TABLE tasks ADD COLUMN last_handoff_id VARCHAR(64)")

    for statement in statements:
        sync_conn.execute(text(statement))

    existing_indexes = {item["name"] for item in inspector.get_indexes("tasks")}
    if "ix_tasks_current_owner_lifeform_id" not in existing_indexes:
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_current_owner_lifeform_id ON tasks (current_owner_lifeform_id)"))

    # Phase 1 — Episode / EpisodeStep 表（新 DB 由 create_all 建，旧 DB 在此补）
    # Phase 2 — policies 表（由 create_all 建；旧 DB 在此补）
    if "policies" not in inspector.get_table_names():
        sync_conn.execute(text("""
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                domain TEXT DEFAULT 'general',
                category TEXT DEFAULT 'mode_selection',
                state TEXT DEFAULT 'candidate',
                content TEXT DEFAULT '',
                rule_logic TEXT,
                hit_count INTEGER DEFAULT 0,
                hit_success INTEGER DEFAULT 0,
                hit_fail INTEGER DEFAULT 0,
                shadow_predictions INTEGER DEFAULT 0,
                shadow_correct INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                last_hit_at TIMESTAMP,
                activated_at TIMESTAMP,
                retired_at TIMESTAMP,
                source TEXT DEFAULT 'seed'
            )
        """))
        sync_conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_policies_domain_state ON policies (domain, state)"
        ))

    # Phase 1 — Episode / EpisodeStep 由 create_all 建表和索引。
    # _bootstrap_compat_schema 只在表不存在时补 kill_marks 的新字段。
    if "kill_marks" in inspector.get_table_names():
        _km_cols = {c["name"] for c in inspector.get_columns("kill_marks")}
        for col_ddl in [
            "ALTER TABLE kill_marks ADD COLUMN episode_id TEXT",
            "ALTER TABLE kill_marks ADD COLUMN episode_step_id TEXT",
            "ALTER TABLE kill_marks ADD COLUMN drain_category TEXT",
        ]:
            col_name = col_ddl.split("COLUMN ")[1].split(" ")[0]
            if col_name not in _km_cols:
                sync_conn.execute(text(col_ddl))
