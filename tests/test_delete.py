"""任务删除 API 测试 —— DELETE /api/tasks/{id}, /api/tasks/bulk, /api/tasks/cleanup"""

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base
from greyfield_hive.services.event_bus import EventBus, TOPIC_TASK_DELETED


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


# ── 辅助 ────────────────────────────────────────────────────────────────

async def _create(client, title: str = "测试任务", **kwargs) -> dict:
    r = await client.post("/api/tasks", json={"title": title, **kwargs})
    assert r.status_code == 201
    return r.json()


# ── 单任务删除 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_task_returns_204(client):
    """删除存在的任务返回 204"""
    task = await _create(client, "待删除的任务")
    r = await client.delete(f"/api/tasks/{task['id']}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_task_removes_from_list(client):
    """删除后任务不再出现在列表中"""
    task = await _create(client, "待删除的任务")
    await client.delete(f"/api/tasks/{task['id']}")
    r = await client.get("/api/tasks")
    ids = [t["id"] for t in r.json()]
    assert task["id"] not in ids


@pytest.mark.asyncio
async def test_delete_task_returns_404_for_missing(client):
    """删除不存在的任务返回 404"""
    r = await client.delete("/api/tasks/BT-不存在-000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_second_call_returns_404(client):
    """同一任务删除两次，第二次返回 404"""
    task = await _create(client)
    await client.delete(f"/api/tasks/{task['id']}")
    r2 = await client.delete(f"/api/tasks/{task['id']}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_leaves_other_tasks_intact(client):
    """删除一个任务，其他任务不受影响"""
    t1 = await _create(client, "任务1")
    t2 = await _create(client, "任务2")
    await client.delete(f"/api/tasks/{t1['id']}")
    r = await client.get("/api/tasks")
    ids = [t["id"] for t in r.json()]
    assert t1["id"] not in ids
    assert t2["id"] in ids


# ── 批量删除 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_delete_returns_count(client):
    """批量删除返回正确的删除数量"""
    t1 = await _create(client, "任务A")
    t2 = await _create(client, "任务B")
    r = await client.request(
        "DELETE", "/api/tasks/bulk",
        json={"task_ids": [t1["id"], t2["id"]]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] == 2
    assert data["not_found"] == []


@pytest.mark.asyncio
async def test_bulk_delete_partial_not_found(client):
    """批量删除时部分 ID 不存在，返回 not_found 列表"""
    t1 = await _create(client, "任务C")
    r = await client.request(
        "DELETE", "/api/tasks/bulk",
        json={"task_ids": [t1["id"], "BT-不存在-ZZZZZZ"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] == 1
    assert "BT-不存在-ZZZZZZ" in data["not_found"]


@pytest.mark.asyncio
async def test_bulk_delete_removes_tasks(client):
    """批量删除后任务全部消失"""
    t1 = await _create(client, "任务X")
    t2 = await _create(client, "任务Y")
    await client.request(
        "DELETE", "/api/tasks/bulk",
        json={"task_ids": [t1["id"], t2["id"]]},
    )
    r = await client.get("/api/tasks")
    assert r.json() == []


@pytest.mark.asyncio
async def test_bulk_delete_empty_list(client):
    """批量删除空列表返回 deleted=0"""
    r = await client.request("DELETE", "/api/tasks/bulk", json={"task_ids": []})
    assert r.status_code == 200
    assert r.json()["deleted"] == 0


# ── 按时间清理 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup_removes_old_completed_tasks(client):
    """cleanup 删除指定天数前已完成的任务"""
    from datetime import timedelta, timezone, datetime
    from greyfield_hive.db import SessionLocal
    from greyfield_hive.models.task import Task, TaskState
    from sqlalchemy import select

    task = await _create(client, "旧的完成任务")
    task_id = task["id"]
    # 流转到 Complete
    for state in ["Planning", "Reviewing", "Spawning", "Executing", "Consolidating", "Complete"]:
        await client.post(f"/api/tasks/{task_id}/transition", json={"new_state": state, "agent": "test"})

    # 强制 updated_at 往回拨 35 天
    async with SessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        t = result.scalar_one()
        t.updated_at = datetime.now(timezone.utc) - timedelta(days=35)
        await db.commit()

    r = await client.delete("/api/tasks/cleanup?days=30")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] >= 1

    r2 = await client.get(f"/api/tasks/{task_id}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_cleanup_keeps_recent_tasks(client):
    """cleanup 不删除未超过天数的任务"""
    task = await _create(client, "新完成任务")
    task_id = task["id"]
    for state in ["Planning", "Reviewing", "Spawning", "Executing", "Consolidating", "Complete"]:
        await client.post(f"/api/tasks/{task_id}/transition", json={"new_state": state, "agent": "test"})

    r = await client.delete("/api/tasks/cleanup?days=30")
    assert r.status_code == 200

    # 刚完成的任务不应被删除
    r2 = await client.get(f"/api/tasks/{task_id}")
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_keeps_active_tasks(client):
    """cleanup 不删除活跃任务（非 Complete/Cancelled）"""
    from datetime import timedelta, timezone, datetime
    from greyfield_hive.db import SessionLocal
    from greyfield_hive.models.task import Task
    from sqlalchemy import select

    task = await _create(client, "活跃任务")
    task_id = task["id"]
    # 流转到 Planning（非终态）
    await client.post(f"/api/tasks/{task_id}/transition", json={"new_state": "Planning", "agent": "test"})

    # 往回拨 60 天
    async with SessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        t = result.scalar_one()
        t.updated_at = datetime.now(timezone.utc) - timedelta(days=60)
        await db.commit()

    r = await client.delete("/api/tasks/cleanup?days=30")
    assert r.status_code == 200
    # 活跃任务不受影响
    r2 = await client.get(f"/api/tasks/{task_id}")
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_default_days(client):
    """cleanup 不带参数，默认 30 天"""
    r = await client.delete("/api/tasks/cleanup")
    assert r.status_code == 200
    assert "deleted" in r.json()


# ── task.deleted 事件广播 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_publishes_task_deleted_event(client):
    """删除任务后，事件总线广播 task.deleted 事件"""
    from greyfield_hive.services.event_bus import get_event_bus

    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_DELETED)
    try:
        task = await _create(client, "事件测试任务")
        r = await client.delete(f"/api/tasks/{task['id']}")
        assert r.status_code == 204
        event = await asyncio.wait_for(q.get(), timeout=2.0)
        assert event.payload["task_id"] == task["id"]
        assert event.payload["title"] == "事件测试任务"
    finally:
        bus.unsubscribe(TOPIC_TASK_DELETED, q)


@pytest.mark.asyncio
async def test_bulk_delete_publishes_events_for_each(client):
    """批量删除时，每个被删除任务都触发 task.deleted 事件"""
    from greyfield_hive.services.event_bus import get_event_bus

    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_DELETED)
    try:
        t1 = await _create(client, "批量删除A")
        t2 = await _create(client, "批量删除B")
        r = await client.request(
            "DELETE", "/api/tasks/bulk",
            json={"task_ids": [t1["id"], t2["id"]]},
        )
        assert r.status_code == 200
        # 等待两个事件
        received_ids: list[str] = []
        for _ in range(2):
            event = await asyncio.wait_for(q.get(), timeout=2.0)
            received_ids.append(event.payload["task_id"])
        assert t1["id"] in received_ids
        assert t2["id"] in received_ids
    finally:
        bus.unsubscribe(TOPIC_TASK_DELETED, q)
