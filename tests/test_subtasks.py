"""子任务分解测试 —— parent_id + GET /children + root_only 过滤"""

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


async def _create(client, title, **kwargs):
    r = await client.post("/api/tasks", json={"title": title, **kwargs})
    assert r.status_code in (200, 201), r.text
    return r.json()


# ── 创建子任务 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_subtask_with_parent_id(client):
    """创建子任务时指定 parent_id，返回值包含 parent_id"""
    parent = await _create(client, "父任务")
    child = await _create(client, "子任务A", parent_id=parent["id"])
    assert child["parent_id"] == parent["id"]


@pytest.mark.asyncio
async def test_create_task_without_parent_id_is_none(client):
    """不指定 parent_id 时为 None"""
    task = await _create(client, "顶层任务")
    assert task["parent_id"] is None


@pytest.mark.asyncio
async def test_create_subtask_invalid_parent_id_404(client):
    """指定不存在的 parent_id 应返回 404"""
    r = await client.post("/api/tasks", json={"title": "孤儿", "parent_id": "BT-99999999-XXXXXX"})
    assert r.status_code == 404


# ── GET /children ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_children_returns_direct_subtasks(client):
    """GET /api/tasks/{id}/children 返回所有直接子任务"""
    parent = await _create(client, "父任务")
    c1 = await _create(client, "子任务1", parent_id=parent["id"])
    c2 = await _create(client, "子任务2", parent_id=parent["id"])

    r = await client.get(f"/api/tasks/{parent['id']}/children")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert c1["id"] in ids
    assert c2["id"] in ids


@pytest.mark.asyncio
async def test_get_children_returns_empty_for_no_children(client):
    """没有子任务时返回空列表"""
    task = await _create(client, "叶节点任务")
    r = await client.get(f"/api/tasks/{task['id']}/children")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_children_404_for_missing_task(client):
    """父任务不存在时返回 404"""
    r = await client.get("/api/tasks/BT-99999999-XXXXXX/children")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_children_does_not_return_grandchildren(client):
    """children 端点只返回直接子任务，不递归返回孙任务"""
    parent = await _create(client, "父")
    child = await _create(client, "子", parent_id=parent["id"])
    await _create(client, "孙", parent_id=child["id"])

    r = await client.get(f"/api/tasks/{parent['id']}/children")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == child["id"]


# ── list_tasks 过滤 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_list_tasks_filter_by_parent_id(client):
    """?parent_id=xxx 只返回该父任务下的子任务"""
    p1 = await _create(client, "父1")
    p2 = await _create(client, "父2")
    await _create(client, "子A", parent_id=p1["id"])
    await _create(client, "子B", parent_id=p1["id"])
    await _create(client, "子C", parent_id=p2["id"])

    r = await client.get(f"/api/tasks?parent_id={p1['id']}")
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert "子A" in titles
    assert "子B" in titles
    assert "子C" not in titles


@pytest.mark.asyncio
async def test_list_tasks_root_only(client):
    """?root_only=true 只返回顶层任务（parent_id 为 null）"""
    root = await _create(client, "顶层任务")
    parent = await _create(client, "另一顶层")
    await _create(client, "子任务", parent_id=parent["id"])

    r = await client.get("/api/tasks?root_only=true")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert root["id"] in ids
    assert parent["id"] in ids
    # 子任务不在结果中
    for t in r.json():
        assert t["parent_id"] is None


# ── parent_id 包含在 GET 单任务和列表响应中 ───────────────

@pytest.mark.asyncio
async def test_get_task_includes_parent_id(client):
    """GET /api/tasks/{id} 包含 parent_id 字段"""
    parent = await _create(client, "父")
    child = await _create(client, "子", parent_id=parent["id"])

    r = await client.get(f"/api/tasks/{child['id']}")
    assert r.status_code == 200
    assert r.json()["parent_id"] == parent["id"]


@pytest.mark.asyncio
async def test_list_tasks_includes_parent_id_field(client):
    """任务列表中每个任务都包含 parent_id 字段"""
    await _create(client, "任务X")
    r = await client.get("/api/tasks")
    assert r.status_code == 200
    for t in r.json():
        assert "parent_id" in t
