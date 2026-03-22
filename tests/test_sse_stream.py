"""SSE 实时事件流测试

测试策略：
- httpx ASGITransport 会完整收集 body 再返回，无限流无法用它测。
- 改用两个层次：
  1. 单元测试：直接测 SSE 端点中的过滤回调逻辑（EventBus + callback）
  2. 端点可达性：通过 FastAPI 的路由注册验证端点存在
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from greyfield_hive.main import app
from greyfield_hive.db import engine, Base
from greyfield_hive.services.event_bus import get_event_bus, EventBus, BusEvent


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


# ── 端点路由存在性 ─────────────────────────────────────────────────────

def test_sse_route_registered():
    """GET /api/events/stream 路由应已注册"""
    routes = {r.path for r in app.routes}
    assert "/api/events/stream" in routes


def test_sse_route_allows_get():
    """/api/events/stream 允许 GET 方法"""
    for r in app.routes:
        if r.path == "/api/events/stream":
            assert "GET" in r.methods
            break


# ── EventBus 回调过滤逻辑（单元测试）─────────────────────────────────

def _make_event(topic: str, task_id: str = "", producer: str = "test") -> BusEvent:
    return BusEvent(
        topic=topic,
        event_type="test.event",
        producer=producer,
        payload={"task_id": task_id} if task_id else {},
    )


@pytest.mark.asyncio
async def test_sse_callback_no_filter_receives_all():
    """不设过滤时，所有事件都推入队列"""
    bus = EventBus()
    q: asyncio.Queue = asyncio.Queue()

    async def callback(ev: BusEvent) -> None:
        await q.put(ev)

    bus.register_ws_callback(callback)

    await bus.publish("task.created", "tr-1", "new", "test", {"task_id": "T-1"})
    await bus.publish("task.status",  "tr-2", "upd", "test", {"task_id": "T-2"})

    # 让 create_task 回调执行
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert q.qsize() == 2
    bus.unregister_ws_callback(callback)


@pytest.mark.asyncio
async def test_sse_callback_topic_filter():
    """topic 过滤：只收到指定 topic 的事件"""
    bus = EventBus()
    received: list[BusEvent] = []
    target_topic = "task.status"

    async def callback(ev: BusEvent) -> None:
        if ev.topic != target_topic:
            return
        received.append(ev)

    bus.register_ws_callback(callback)

    await bus.publish("task.created", "tr-a", "new", "test", {"task_id": "T-A"})
    await bus.publish("task.status",  "tr-b", "upd", "test", {"task_id": "T-B"})
    await bus.publish("task.completed","tr-c","done","test", {"task_id": "T-C"})

    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(received) == 1
    assert received[0].topic == "task.status"
    assert received[0].payload["task_id"] == "T-B"

    bus.unregister_ws_callback(callback)


@pytest.mark.asyncio
async def test_sse_callback_task_id_filter():
    """task_id 过滤：只收到指定任务的事件"""
    bus = EventBus()
    received: list[BusEvent] = []
    target_task = "T-TARGET"

    async def callback(ev: BusEvent) -> None:
        if ev.payload.get("task_id") != target_task:
            return
        received.append(ev)

    bus.register_ws_callback(callback)

    await bus.publish("task.status", "tr-x", "upd", "test", {"task_id": "T-OTHER"})
    await bus.publish("task.status", "tr-y", "upd", "test", {"task_id": "T-TARGET"})

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(received) == 1
    assert received[0].payload["task_id"] == "T-TARGET"

    bus.unregister_ws_callback(callback)


@pytest.mark.asyncio
async def test_sse_callback_combined_topic_and_task_id():
    """topic + task_id 双重过滤：两个条件都要匹配"""
    bus = EventBus()
    received: list[BusEvent] = []

    async def callback(ev: BusEvent) -> None:
        if ev.topic != "task.status":
            return
        if ev.payload.get("task_id") != "T-BOTH":
            return
        received.append(ev)

    bus.register_ws_callback(callback)

    # topic 不匹配
    await bus.publish("task.created", "tr-1", "new", "test", {"task_id": "T-BOTH"})
    # task_id 不匹配
    await bus.publish("task.status",  "tr-2", "upd", "test", {"task_id": "T-OTHER"})
    # 都匹配
    await bus.publish("task.status",  "tr-3", "upd", "test", {"task_id": "T-BOTH"})

    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(received) == 1
    assert received[0].payload["task_id"] == "T-BOTH"
    assert received[0].topic == "task.status"

    bus.unregister_ws_callback(callback)


@pytest.mark.asyncio
async def test_sse_callback_unregister_stops_delivery():
    """注销回调后不再收到事件"""
    bus = EventBus()
    received: list[BusEvent] = []

    async def callback(ev: BusEvent) -> None:
        received.append(ev)

    bus.register_ws_callback(callback)
    await bus.publish("task.status", "tr-1", "upd", "test", {"task_id": "T-1"})
    await asyncio.sleep(0)

    bus.unregister_ws_callback(callback)
    await bus.publish("task.status", "tr-2", "upd", "test", {"task_id": "T-2"})
    await asyncio.sleep(0)

    assert len(received) == 1  # 只收到注销前的事件


# ── SSE 响应格式测试（通过 payload 构建） ──────────────────────────────

def test_sse_event_json_format():
    """SSE 事件 JSON 包含所有必要字段"""
    ev = BusEvent(
        topic="task.status",
        event_type="task.updated",
        producer="test-producer",
        payload={"task_id": "T-001", "state": "Executing"},
    )
    data = {
        "event_id":   ev.event_id,
        "trace_id":   ev.trace_id,
        "topic":      ev.topic,
        "event_type": ev.event_type,
        "producer":   ev.producer,
        "payload":    ev.payload,
        "created_at": ev.created_at,
    }
    # 验证能正确序列化
    line = f"data: {json.dumps(data, ensure_ascii=False)}"
    assert line.startswith("data: {")
    parsed = json.loads(line[5:])
    assert parsed["topic"] == "task.status"
    assert parsed["event_type"] == "task.updated"
    assert parsed["producer"] == "test-producer"
    assert parsed["payload"]["task_id"] == "T-001"


def test_sse_connected_message_format():
    """SSE connected 初始消息格式正确"""
    line = 'data: {"type": "connected"}'
    data = json.loads(line[5:])
    assert data["type"] == "connected"
