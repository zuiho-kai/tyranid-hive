"""分页 + 总数测试 —— X-Total-Count 响应头 + GET /count 端点"""

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


async def _create(client, title, **kwargs) -> dict:
    r = await client.post("/api/tasks", json={"title": title, **kwargs})
    assert r.status_code in (200, 201)
    return r.json()


# ── X-Total-Count header ──────────────────────────────────

@pytest.mark.asyncio
async def test_list_tasks_returns_total_count_header(client):
    """GET /api/tasks 响应头包含 X-Total-Count"""
    await _create(client, "任务A")
    await _create(client, "任务B")
    await _create(client, "任务C")

    r = await client.get("/api/tasks")
    assert r.status_code == 200
    assert "x-total-count" in r.headers
    assert int(r.headers["x-total-count"]) == 3


@pytest.mark.asyncio
async def test_total_count_header_matches_unfiltered_total(client):
    """X-Total-Count 反映全量数量，不受 limit 影响"""
    for i in range(5):
        await _create(client, f"任务{i}")

    # limit=2，但 total 应为 5
    r = await client.get("/api/tasks?limit=2&offset=0")
    assert len(r.json()) == 2
    assert int(r.headers["x-total-count"]) == 5


@pytest.mark.asyncio
async def test_total_count_header_respects_filters(client):
    """X-Total-Count 与过滤条件一致"""
    await _create(client, "高优先级1", priority="high")
    await _create(client, "高优先级2", priority="high")
    await _create(client, "普通任务",  priority="normal")

    r = await client.get("/api/tasks?priority=high")
    assert r.status_code == 200
    assert int(r.headers["x-total-count"]) == 2
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_total_count_header_empty(client):
    """无任务时 X-Total-Count 为 0"""
    r = await client.get("/api/tasks")
    assert r.status_code == 200
    assert int(r.headers["x-total-count"]) == 0


# ── GET /count endpoint ───────────────────────────────────

@pytest.mark.asyncio
async def test_count_endpoint_returns_total(client):
    """GET /api/tasks/count 返回 {total: N}"""
    await _create(client, "T1")
    await _create(client, "T2")

    r = await client.get("/api/tasks/count")
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_count_endpoint_with_state_filter(client):
    """GET /api/tasks/count?state=Incubating 按状态计数"""
    await _create(client, "T1")
    await _create(client, "T2")

    r = await client.get("/api/tasks/count?state=Incubating")
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_count_endpoint_with_label_filter(client):
    """GET /api/tasks/count?label=urgent 按标签计数"""
    await _create(client, "T1", labels=["urgent"])
    await _create(client, "T2", labels=["urgent", "bug"])
    await _create(client, "T3", labels=["bug"])

    r = await client.get("/api/tasks/count?label=urgent")
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_count_endpoint_root_only(client):
    """GET /api/tasks/count?root_only=true 只计顶层任务"""
    parent = await _create(client, "父任务")
    await _create(client, "子任务", parent_id=parent["id"])
    await _create(client, "另一顶层")

    r = await client.get("/api/tasks/count?root_only=true")
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_count_endpoint_empty(client):
    """GET /api/tasks/count 无任务时返回 0"""
    r = await client.get("/api/tasks/count")
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ── pagination with offset ────────────────────────────────

@pytest.mark.asyncio
async def test_pagination_offset(client):
    """limit+offset 分页正确，总数不变"""
    for i in range(7):
        await _create(client, f"任务{i:02d}")

    r1 = await client.get("/api/tasks?limit=3&offset=0")
    r2 = await client.get("/api/tasks?limit=3&offset=3")
    r3 = await client.get("/api/tasks?limit=3&offset=6")

    assert len(r1.json()) == 3
    assert len(r2.json()) == 3
    assert len(r3.json()) == 1
    # 所有分页的 X-Total-Count 都是 7
    for r in [r1, r2, r3]:
        assert int(r.headers["x-total-count"]) == 7
