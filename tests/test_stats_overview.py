"""综合统计 API 测试 —— GET /api/stats/overview"""

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


# ── 空库 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_empty(client):
    """空数据库时各统计应为零"""
    r = await client.get("/api/stats/overview")
    assert r.status_code == 200
    data = r.json()

    assert data["tasks"]["total"] == 0
    assert data["tasks"]["by_state"] == {}
    assert data["lessons"]["total"] == 0
    assert data["lessons"]["by_domain"] == {}
    assert data["lessons"]["by_outcome"] == {}
    assert data["lessons"]["top_active"] == []
    assert data["playbooks"]["total"] == 0
    assert data["playbooks"]["active"] == 0
    assert data["playbooks"]["crystallized"] == 0
    assert data["playbooks"]["by_domain"] == {}


# ── 任务统计 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_counts_tasks(client):
    """创建任务后 tasks.total 和 by_state 应正确"""
    await client.post("/api/tasks", json={"title": "T1"})
    await client.post("/api/tasks", json={"title": "T2"})

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["tasks"]["total"] == 2
    assert data["tasks"]["by_state"].get("Incubating", 0) == 2


@pytest.mark.asyncio
async def test_overview_tasks_by_state(client):
    """状态流转后 by_state 应反映最新状态"""
    r = await client.post("/api/tasks", json={"title": "T1"})
    task_id = r.json()["id"]
    await client.post(f"/api/tasks/{task_id}/transition", json={"new_state": "Planning", "agent": "test", "reason": ""})

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["tasks"]["by_state"].get("Planning", 0) == 1
    assert data["tasks"]["by_state"].get("Incubating", 0) == 0


# ── 经验库统计 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_counts_lessons(client):
    """添加经验后 lessons.total 和 by_domain 应正确"""
    await client.post("/api/lessons", json={"domain": "coding", "content": "经验A", "outcome": "success"})
    await client.post("/api/lessons", json={"domain": "coding", "content": "经验B", "outcome": "failure"})
    await client.post("/api/lessons", json={"domain": "devops", "content": "经验C", "outcome": "success"})

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["lessons"]["total"] == 3
    assert data["lessons"]["by_domain"]["coding"] == 2
    assert data["lessons"]["by_domain"]["devops"] == 1


@pytest.mark.asyncio
async def test_overview_lessons_by_outcome(client):
    """by_outcome 应正确统计各结果数量"""
    await client.post("/api/lessons", json={"domain": "coding", "content": "A", "outcome": "success"})
    await client.post("/api/lessons", json={"domain": "coding", "content": "B", "outcome": "failure"})
    await client.post("/api/lessons", json={"domain": "coding", "content": "C", "outcome": "success"})

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["lessons"]["by_outcome"]["success"] == 2
    assert data["lessons"]["by_outcome"]["failure"] == 1


@pytest.mark.asyncio
async def test_overview_top_active_lessons(client):
    """top_active 应按 frequency 降序排列，最多 5 条"""
    # 创建 3 条经验并 bump
    ids = []
    for i in range(3):
        r = await client.post("/api/lessons", json={"domain": "test", "content": f"经验{i}", "outcome": "success"})
        ids.append(r.json()["id"])

    # bump：l0=3次，l1=1次，l2=2次
    for _ in range(3):
        await client.post(f"/api/lessons/{ids[0]}/bump")
    await client.post(f"/api/lessons/{ids[1]}/bump")
    for _ in range(2):
        await client.post(f"/api/lessons/{ids[2]}/bump")

    r = await client.get("/api/stats/overview")
    data = r.json()
    top = data["lessons"]["top_active"]
    assert len(top) <= 5
    assert top[0]["id"] == ids[0]       # frequency=3 最高
    assert top[1]["id"] == ids[2]       # frequency=2
    assert top[2]["id"] == ids[1]       # frequency=1


# ── 作战手册统计 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_counts_playbooks(client):
    """创建手册后 playbooks.total 和 active 应正确"""
    await client.post("/api/playbooks", json={"slug": "pb1", "domain": "coding", "title": "手册1", "content": "内容"})
    await client.post("/api/playbooks", json={"slug": "pb2", "domain": "devops", "title": "手册2", "content": "内容"})

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["playbooks"]["total"] == 2
    assert data["playbooks"]["active"] == 2
    assert data["playbooks"]["crystallized"] == 0


@pytest.mark.asyncio
async def test_overview_crystallized_count(client):
    """手册结晶后 crystallized 计数应增加"""
    r = await client.post("/api/playbooks", json={"slug": "pb1", "domain": "coding", "title": "手册1", "content": "内容"})
    pb_id = r.json()["id"]
    await client.post(f"/api/playbooks/{pb_id}/crystallize")

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["playbooks"]["crystallized"] == 1


@pytest.mark.asyncio
async def test_overview_inactive_playbooks_excluded_from_active(client):
    """归档的手册不计入 active，但仍计入 total"""
    r = await client.post("/api/playbooks", json={"slug": "pb1", "domain": "coding", "title": "手册1", "content": "内容"})
    pb_id = r.json()["id"]
    await client.post(f"/api/playbooks/{pb_id}/deactivate")

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["playbooks"]["total"] == 1
    assert data["playbooks"]["active"] == 0


@pytest.mark.asyncio
async def test_overview_playbooks_by_domain(client):
    """by_domain 只统计活跃手册"""
    await client.post("/api/playbooks", json={"slug": "pb1", "domain": "coding", "title": "A", "content": "x"})
    await client.post("/api/playbooks", json={"slug": "pb2", "domain": "coding", "title": "B", "content": "x"})
    await client.post("/api/playbooks", json={"slug": "pb3", "domain": "devops", "title": "C", "content": "x"})

    r = await client.get("/api/stats/overview")
    data = r.json()
    assert data["playbooks"]["by_domain"]["coding"] == 2
    assert data["playbooks"]["by_domain"]["devops"] == 1
