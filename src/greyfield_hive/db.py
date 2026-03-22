"""数据库初始化 —— SQLAlchemy async + SQLite（可升级 Postgres）"""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# DB 路径优先读环境变量
_db_path = os.environ.get("HIVE_DB_PATH", "data/hive.db")
Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "HIVE_DATABASE_URL",
    f"sqlite+aiosqlite:///{_db_path}",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=os.environ.get("HIVE_DB_ECHO", "0") == "1",
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """创建所有表（若不存在）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """FastAPI Depends 注入"""
    async with SessionLocal() as session:
        yield session
