"""任务依赖阻塞测试 —— depends_on + is_blocked + GET /blocked"""

import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base, SessionLocal
from greyfield_hive.services.task_service import TaskService
from greyfield_hive.models.task import TaskState


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
    assert r.status_code in (200, 201), r.text
    return r.json()


# ── 创建时指定 depends_on ────────────────────────────────

@pytest.mark.asyncio
async def test_create_task_with_depends_on(client):
    """创建任务时可指定 depends_on，返回值包含 depends_on"""
    dep = await _create(client, "依赖任务")
    task = await _create(client, "等待任务", depends_on=[dep["id"]])
    assert dep["id"] in task["depends_on"]


@pytest.mark.asyncio
async def test_create_task_without_depends_on_defaults_empty(client):
    """不指定 depends_on 时默认为空列表"""
    task = await _create(client, "普通任务")
    assert task["depends_on"] == []


@pytest.mark.asyncio
async def test_create_task_invalid_dep_returns_404(client):
    """depends_on 中包含不存在的任务 ID 时返回 404"""
    r = await client.post("/api/tasks", json={"title": "孤儿", "depends_on": ["BT-NOTEXIST-000000"]})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_depends_on_included_in_list_response(client):
    """任务列表中每个任务都包含 depends_on 字段"""
    await _create(client, "T1")
    r = await client.get("/api/tasks")
    assert r.status_code == 200
    for t in r.json():
        assert "depends_on" in t
        assert isinstance(t["depends_on"], list)


# ── GET /blocked ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_blocked_endpoint_when_dep_not_complete(client):
    """依赖任务未完成时，/blocked 返回 is_blocked=True"""
    dep = await _create(client, "依赖任务")
    task = await _create(client, "阻塞任务", depends_on=[dep["id"]])

    r = await client.get(f"/api/tasks/{task['id']}/blocked")
    assert r.status_code == 200
    data = r.json()
    assert data["is_blocked"] is True
    assert any(d["id"] == dep["id"] for d in data["pending_deps"])


@pytest.mark.asyncio
async def test_blocked_endpoint_when_dep_complete(client):
    """依赖任务已完成时，/blocked 返回 is_blocked=False"""
    dep = await _create(client, "已完成依赖")
    task = await _create(client, "解锁任务", depends_on=[dep["id"]])

    # 将依赖任务推进到 Complete（需要先经过中间状态）
    async with SessionLocal() as db:
        svc = TaskService(db)
        dep_task = await svc.get_by_id(dep["id"])
        dep_task.state = TaskState.Complete
        await db.commit()

    r = await client.get(f"/api/tasks/{task['id']}/blocked")
    assert r.status_code == 200
    assert r.json()["is_blocked"] is False
    assert r.json()["pending_deps"] == []


@pytest.mark.asyncio
async def test_blocked_endpoint_no_deps(client):
    """无依赖任务时，/blocked 返回 is_blocked=False"""
    task = await _create(client, "无依赖")
    r = await client.get(f"/api/tasks/{task['id']}/blocked")
    assert r.status_code == 200
    assert r.json()["is_blocked"] is False
    assert r.json()["pending_deps"] == []


@pytest.mark.asyncio
async def test_blocked_endpoint_404_for_missing_task(client):
    """任务不存在时返回 404"""
    r = await client.get("/api/tasks/BT-NOTEXIST-000000/blocked")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_blocked_partial_deps_complete(client):
    """多个依赖中部分已完成：仍阻塞，只列出未完成的"""
    dep1 = await _create(client, "依赖1")
    dep2 = await _create(client, "依赖2")
    task = await _create(client, "多依赖任务", depends_on=[dep1["id"], dep2["id"]])

    # 将 dep1 完成
    async with SessionLocal() as db:
        svc = TaskService(db)
        d1 = await svc.get_by_id(dep1["id"])
        d1.state = TaskState.Complete
        await db.commit()

    r = await client.get(f"/api/tasks/{task['id']}/blocked")
    data = r.json()
    assert data["is_blocked"] is True
    pending_ids = [d["id"] for d in data["pending_deps"]]
    assert dep1["id"] not in pending_ids   # 已完成，不在 pending
    assert dep2["id"] in pending_ids       # 未完成，在 pending


# ── TaskService.is_blocked ────────────────────────────────

@pytest.mark.asyncio
async def test_is_blocked_service_method():
    """TaskService.is_blocked 直接调用测试"""
    async with SessionLocal() as db:
        svc = TaskService(db)
        dep = await svc.create_task("依赖")
        task = await svc.create_task("阻塞方", depends_on=[dep.id])
        assert await svc.is_blocked(task.id) is True

    # 将依赖改为 Complete
    async with SessionLocal() as db:
        svc = TaskService(db)
        d = await svc.get_by_id(dep.id)
        d.state = TaskState.Complete
        await db.commit()

    async with SessionLocal() as db:
        svc = TaskService(db)
        assert await svc.is_blocked(task.id) is False


# ── TaskService.get_waiting_tasks ─────────────────────────

@pytest.mark.asyncio
async def test_get_waiting_tasks_returns_dependent_tasks():
    """get_waiting_tasks 返回所有依赖指定任务的未完成任务"""
    async with SessionLocal() as db:
        svc = TaskService(db)
        dep = await svc.create_task("被依赖任务")
        w1 = await svc.create_task("等待者1", depends_on=[dep.id])
        w2 = await svc.create_task("等待者2", depends_on=[dep.id])
        unrelated = await svc.create_task("无关任务")

    async with SessionLocal() as db:
        svc = TaskService(db)
        waiting = await svc.get_waiting_tasks(dep.id)
        waiting_ids = [t.id for t in waiting]
        assert w1.id in waiting_ids
        assert w2.id in waiting_ids
        assert unrelated.id not in waiting_ids
