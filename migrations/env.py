"""Alembic 异步迁移环境配置

支持 SQLite（开发）和 PostgreSQL（生产），通过 HIVE_DATABASE_URL 环境变量切换。

使用方法：
  # 升级到最新版本
  alembic upgrade head

  # 生成新迁移（修改 model 后）
  alembic revision --autogenerate -m "描述变更"

  # 查看迁移状态
  alembic current
  alembic history
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ── 加载项目 Base 和所有 Model ──────────────────────────────
# 确保所有 Model 在 metadata 中注册
from greyfield_hive.db import Base, _build_database_url, _build_engine_kwargs  # noqa: F401
import greyfield_hive.models.task      # noqa: F401
import greyfield_hive.models.lesson    # noqa: F401
import greyfield_hive.models.playbook  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 从环境变量读取 URL（覆盖 alembic.ini 中的占位符）
_url = _build_database_url()


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库（用于 dry-run 或审核）"""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # PostgreSQL 专用：使用 schema 前缀
        # include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移"""
    engine_kwargs = _build_engine_kwargs(_url)
    # 迁移时不需要连接池
    engine_kwargs.pop("pool_size", None)
    engine_kwargs.pop("max_overflow", None)
    engine_kwargs.pop("pool_timeout", None)
    engine_kwargs.pop("pool_recycle", None)
    engine_kwargs.pop("pool_pre_ping", None)

    connectable = create_async_engine(_url, **engine_kwargs)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
