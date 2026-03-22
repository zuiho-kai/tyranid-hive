"""任务列表排序测试 —— GET /api/tasks?sort_by=X&order=Y"""

import asyncio
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


async def _create(client, title: str, priority: str = "normal") -> dict:
    r = await client.post("/api/tasks", json={"title": title, "priority": priority})
    assert r.status_code == 201
    return r.json()


# ── 默认排序（updated_at desc）────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_sort_is_updated_at_desc(client):
    """默认按 updated_at 降序（最新在前）"""
    t1 = await _create(client, "第一个任务")
    await asyncio.sleep(0.01)
    t2 = await _create(client, "第二个任务")
    r = await client.get("/api/tasks")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert ids.index(t2["id"]) < ids.index(t1["id"])


# ── created_at 排序 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_by_created_at_desc(client):
    """按 created_at 降序"""
    t1 = await _create(client, "任务A")
    await asyncio.sleep(0.01)
    t2 = await _create(client, "任务B")
    r = await client.get("/api/tasks?sort_by=created_at&order=desc")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert ids.index(t2["id"]) < ids.index(t1["id"])


@pytest.mark.asyncio
async def test_sort_by_created_at_asc(client):
    """按 created_at 升序（最旧在前）"""
    t1 = await _create(client, "任务A")
    await asyncio.sleep(0.01)
    t2 = await _create(client, "任务B")
    r = await client.get("/api/tasks?sort_by=created_at&order=asc")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert ids.index(t1["id"]) < ids.index(t2["id"])


# ── priority 排序 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_by_priority_asc(client):
    """按优先级升序（critical 在前）"""
    await _create(client, "低优任务", priority="low")
    await _create(client, "普通任务", priority="normal")
    await _create(client, "紧急任务", priority="critical")
    await _create(client, "高优任务", priority="high")

    r = await client.get("/api/tasks?sort_by=priority&order=asc")
    assert r.status_code == 200
    tasks = r.json()
    priorities = [t["priority"] for t in tasks]
    # critical(0) → high(1) → normal(2) → low(3)
    order_map = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    for i in range(len(priorities) - 1):
        assert order_map[priorities[i]] <= order_map[priorities[i + 1]]


@pytest.mark.asyncio
async def test_sort_by_priority_desc(client):
    """按优先级降序（low 在前）"""
    await _create(client, "低优任务", priority="low")
    await _create(client, "紧急任务", priority="critical")

    r = await client.get("/api/tasks?sort_by=priority&order=desc")
    assert r.status_code == 200
    tasks = r.json()
    priorities = [t["priority"] for t in tasks]
    # low(3) → critical(0)
    order_map = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    for i in range(len(priorities) - 1):
        assert order_map[priorities[i]] >= order_map[priorities[i + 1]]


# ── state 排序 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_by_state_asc(client):
    """按 state 升序（字母序）"""
    t1 = await _create(client, "任务X")
    await client.post(f"/api/tasks/{t1['id']}/transition", json={"new_state": "Planning", "agent": "test"})
    await _create(client, "任务Y")  # Incubating

    r = await client.get("/api/tasks?sort_by=state&order=asc")
    assert r.status_code == 200
    states = [t["state"] for t in r.json()]
    assert states == sorted(states)


# ── 非法参数 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_sort_by_returns_400(client):
    """无效 sort_by 返回 400"""
    r = await client.get("/api/tasks?sort_by=banana")
    assert r.status_code == 400
    assert "sort_by" in r.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_order_returns_400(client):
    """无效 order 返回 400"""
    r = await client.get("/api/tasks?order=sideways")
    assert r.status_code == 400
    assert "order" in r.json()["detail"]


# ── 与其他过滤器组合 ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_combined_with_state_filter(client):
    """sort_by + state 过滤可以同时使用"""
    t1 = await _create(client, "任务A", priority="high")
    await client.post(f"/api/tasks/{t1['id']}/transition", json={"new_state": "Planning", "agent": "test"})
    t2 = await _create(client, "任务B", priority="critical")
    await client.post(f"/api/tasks/{t2['id']}/transition", json={"new_state": "Planning", "agent": "test"})
    await _create(client, "任务C", priority="normal")  # Incubating, filtered out

    r = await client.get("/api/tasks?state=Planning&sort_by=priority&order=asc")
    assert r.status_code == 200
    tasks = r.json()
    assert all(t["state"] == "Planning" for t in tasks)
    assert len(tasks) == 2
    assert tasks[0]["priority"] == "critical"
    assert tasks[1]["priority"] == "high"
