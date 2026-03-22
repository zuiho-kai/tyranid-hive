"""数据库配置测试 —— 不需要真实 PostgreSQL 连接"""

import os
import pytest


# ── _build_database_url ───────────────────────────────────

def test_default_sqlite_url(monkeypatch, tmp_path):
    """未设置任何环境变量时，默认使用 SQLite"""
    monkeypatch.delenv("HIVE_DATABASE_URL", raising=False)
    monkeypatch.setenv("HIVE_DB_PATH", str(tmp_path / "test.db"))

    from greyfield_hive.db import _build_database_url
    url = _build_database_url()
    assert "sqlite+aiosqlite" in url
    assert "test.db" in url


def test_explicit_postgres_url(monkeypatch):
    """设置 HIVE_DATABASE_URL 时直接使用"""
    pg_url = "postgresql+asyncpg://user:pass@localhost/testdb"
    monkeypatch.setenv("HIVE_DATABASE_URL", pg_url)

    from greyfield_hive.db import _build_database_url
    url = _build_database_url()
    assert url == pg_url


def test_explicit_sqlite_url_overrides_db_path(monkeypatch, tmp_path):
    """HIVE_DATABASE_URL 优先于 HIVE_DB_PATH"""
    monkeypatch.setenv("HIVE_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/explicit.db")
    monkeypatch.setenv("HIVE_DB_PATH", str(tmp_path / "other.db"))

    from greyfield_hive.db import _build_database_url
    url = _build_database_url()
    assert "explicit.db" in url
    assert "other.db" not in url


# ── _is_postgres ──────────────────────────────────────────

def test_is_postgres_with_postgresql():
    from greyfield_hive.db import _is_postgres
    assert _is_postgres("postgresql+asyncpg://user:pass@host/db") is True


def test_is_postgres_with_postgres_shorthand():
    from greyfield_hive.db import _is_postgres
    assert _is_postgres("postgres://user:pass@host/db") is True


def test_is_postgres_sqlite_returns_false():
    from greyfield_hive.db import _is_postgres
    assert _is_postgres("sqlite+aiosqlite:///data/hive.db") is False


# ── _build_engine_kwargs ──────────────────────────────────

def test_sqlite_engine_kwargs_has_check_same_thread():
    from greyfield_hive.db import _build_engine_kwargs
    kwargs = _build_engine_kwargs("sqlite+aiosqlite:///data/hive.db")
    assert "connect_args" in kwargs
    assert kwargs["connect_args"]["check_same_thread"] is False
    # SQLite 不应有 pool_size
    assert "pool_size" not in kwargs


def test_postgres_engine_kwargs_has_pool_settings(monkeypatch):
    from greyfield_hive.db import _build_engine_kwargs
    # 使用默认池参数
    monkeypatch.delenv("HIVE_DB_POOL_SIZE",    raising=False)
    monkeypatch.delenv("HIVE_DB_MAX_OVERFLOW",  raising=False)
    monkeypatch.delenv("HIVE_DB_POOL_TIMEOUT",  raising=False)
    monkeypatch.delenv("HIVE_DB_POOL_RECYCLE",  raising=False)

    kwargs = _build_engine_kwargs("postgresql+asyncpg://user:pass@host/db")
    assert "pool_size"    in kwargs
    assert "max_overflow" in kwargs
    assert "pool_pre_ping" in kwargs
    assert kwargs["pool_pre_ping"] is True
    # PostgreSQL 不应有 check_same_thread
    assert "connect_args" not in kwargs


def test_postgres_pool_size_from_env(monkeypatch):
    from greyfield_hive.db import _build_engine_kwargs
    monkeypatch.setenv("HIVE_DB_POOL_SIZE", "20")
    kwargs = _build_engine_kwargs("postgresql+asyncpg://user:pass@host/db")
    assert kwargs["pool_size"] == 20


def test_postgres_pool_defaults(monkeypatch):
    from greyfield_hive.db import _build_engine_kwargs
    monkeypatch.delenv("HIVE_DB_POOL_SIZE",    raising=False)
    monkeypatch.delenv("HIVE_DB_MAX_OVERFLOW",  raising=False)
    monkeypatch.delenv("HIVE_DB_POOL_TIMEOUT",  raising=False)
    monkeypatch.delenv("HIVE_DB_POOL_RECYCLE",  raising=False)

    kwargs = _build_engine_kwargs("postgresql+asyncpg://u:p@h/db")
    assert kwargs["pool_size"]    == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_timeout"] == 30
    assert kwargs["pool_recycle"] == 1800


# ── BLOB import 清理验证 ──────────────────────────────────

def test_task_model_no_sqlite_blob_import():
    """task.py 不应再引用 SQLite 专有 BLOB 类型"""
    import greyfield_hive.models.task as task_mod
    assert not hasattr(task_mod, "BLOB"), "BLOB 应已从 task.py 移除"
