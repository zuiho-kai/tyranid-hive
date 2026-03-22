"""Playbook L2 测试 —— 版本管理 + 检索 + 统计"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── 基础 CRUD ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_playbook(client):
    resp = await client.post("/api/playbooks", json={
        "slug": "api-timeout-pattern",
        "domain": "code",
        "title": "API 调用超时处理",
        "content": "调用外部 API 时始终设置 timeout=30，捕获 TimeoutError 后重试一次",
        "tags": ["api", "timeout", "retry"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["is_active"] == True
    assert data["slug"] == "api-timeout-pattern"


@pytest.mark.asyncio
async def test_create_duplicate_slug_fails(client):
    await client.post("/api/playbooks", json={"slug": "dup", "domain": "code", "title": "T", "content": "C"})
    resp = await client.post("/api/playbooks", json={"slug": "dup", "domain": "code", "title": "T2", "content": "C2"})
    assert resp.status_code == 409


# ── 版本管理 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_version(client):
    await client.post("/api/playbooks", json={"slug": "retry-pattern", "domain": "code", "title": "重试", "content": "v1 内容"})

    resp = await client.post("/api/playbooks/slug/retry-pattern/versions", json={
        "content": "v2 内容：加入指数退避策略",
        "notes": "根据 Lesson abc123 优化"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 2
    assert data["is_active"] == True

    # v1 应该已归档
    versions = await client.get("/api/playbooks/slug/retry-pattern/versions")
    all_v = versions.json()
    assert len(all_v) == 2
    v1 = next(v for v in all_v if v["version"] == 1)
    assert v1["is_active"] == False


@pytest.mark.asyncio
async def test_rollback(client):
    await client.post("/api/playbooks", json={"slug": "rollback-test", "domain": "code", "title": "T", "content": "v1"})
    await client.post("/api/playbooks/slug/rollback-test/versions", json={"content": "v2"})

    resp = await client.post("/api/playbooks/slug/rollback-test/rollback/1")
    assert resp.status_code == 200
    assert resp.json()["version"] == 1
    assert resp.json()["is_active"] == True

    # v2 应被归档
    active = await client.get("/api/playbooks/slug/rollback-test")
    assert active.json()["version"] == 1


# ── 检索 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_by_domain(client):
    await client.post("/api/playbooks", json={"slug": "code-pb", "domain": "code", "title": "代码", "content": "c", "tags": ["python"]})
    await client.post("/api/playbooks", json={"slug": "fin-pb", "domain": "finance", "title": "金融", "content": "f"})

    resp = await client.post("/api/playbooks/search", json={"domain": "code", "tags": ["python"]})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["slug"] == "code-pb"


# ── 统计更新 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_usage_updates_stats(client):
    create = await client.post("/api/playbooks", json={"slug": "stats-pb", "domain": "code", "title": "T", "content": "C"})
    pb_id = create.json()["id"]

    # 记录 5 次成功，1 次失败
    for _ in range(5):
        await client.post(f"/api/playbooks/{pb_id}/usage", json={"success": True})
    await client.post(f"/api/playbooks/{pb_id}/usage", json={"success": False})

    resp = await client.get(f"/api/playbooks/{pb_id}")
    data = resp.json()
    assert data["use_count"] == 6
    assert 0 < data["success_rate"] < 1.0  # EMA 介于 0-1


# ── 结晶 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_crystallize(client):
    create = await client.post("/api/playbooks", json={"slug": "crystal-pb", "domain": "code", "title": "T", "content": "C"})
    pb_id = create.json()["id"]

    resp = await client.post(f"/api/playbooks/{pb_id}/crystallize")
    assert resp.status_code == 200
    assert resp.json()["crystallized"] == True
