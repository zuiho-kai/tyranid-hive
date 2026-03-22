"""Lesson 命中频率追踪测试 —— POST /api/lessons/{id}/bump"""

import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _add_lesson(client, domain="coding", content="内容", outcome="success") -> dict:
    r = await client.post("/api/lessons", json={
        "domain": domain, "content": content, "outcome": outcome,
    })
    assert r.status_code == 201
    return r.json()


# ── bump 基本行为 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bump_increments_frequency(client):
    """bump 后 frequency 应从 0 变为 1"""
    lesson = await _add_lesson(client)
    assert lesson["frequency"] == 0

    r = await client.post(f"/api/lessons/{lesson['id']}/bump")
    assert r.status_code == 200
    data = r.json()
    assert data["frequency"] == 1


@pytest.mark.asyncio
async def test_bump_twice_increments_twice(client):
    """连续 bump 两次，frequency 应为 2"""
    lesson = await _add_lesson(client)

    await client.post(f"/api/lessons/{lesson['id']}/bump")
    r = await client.post(f"/api/lessons/{lesson['id']}/bump")
    assert r.status_code == 200
    assert r.json()["frequency"] == 2


@pytest.mark.asyncio
async def test_bump_updates_last_used(client):
    """bump 后 last_used 应被更新（不为 None）"""
    lesson = await _add_lesson(client)

    r = await client.post(f"/api/lessons/{lesson['id']}/bump")
    assert r.status_code == 200
    assert r.json()["last_used"] is not None


@pytest.mark.asyncio
async def test_bump_returns_lesson_fields(client):
    """bump 响应应包含完整 lesson 字段"""
    lesson = await _add_lesson(client, domain="devops", content="运维经验", outcome="failure")

    r = await client.post(f"/api/lessons/{lesson['id']}/bump")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == lesson["id"]
    assert data["domain"] == "devops"
    assert data["content"] == "运维经验"
    assert data["outcome"] == "failure"


@pytest.mark.asyncio
async def test_bump_does_not_affect_other_lessons(client):
    """bump 一个 lesson 不应影响另一个 lesson 的 frequency"""
    l1 = await _add_lesson(client, content="经验 A")
    l2 = await _add_lesson(client, content="经验 B")

    await client.post(f"/api/lessons/{l1['id']}/bump")

    r = await client.get(f"/api/lessons/{l2['id']}")
    assert r.status_code == 200
    assert r.json()["frequency"] == 0


@pytest.mark.asyncio
async def test_bump_nonexistent_lesson(client):
    """bump 不存在的 lesson 应返回 404"""
    r = await client.post("/api/lessons/no-such-id/bump")
    assert r.status_code == 404
