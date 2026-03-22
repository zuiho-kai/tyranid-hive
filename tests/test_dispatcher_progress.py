"""Dispatcher 进度回写集成测试

验证：agent 执行完毕后，输出被回写到 task.progress_log
需要真实 DB（SQLite）+ 真实 EventBus
"""

import asyncio
import pytest

from greyfield_hive.services.event_bus import (
    EventBus,
    TOPIC_TASK_DISPATCH,
    TOPIC_AGENT_THOUGHTS,
    TOPIC_AGENT_HEARTBEAT,
)
from greyfield_hive.workers.dispatcher import DispatchWorker
from greyfield_hive.db import engine, Base, SessionLocal
from greyfield_hive.services.task_service import TaskService


# ── DB fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


async def create_test_task(title: str = "测试战团") -> str:
    """在 DB 中创建测试任务，返回 task_id"""
    async with SessionLocal() as db:
        svc = TaskService(db)
        task = await svc.create_task(title=title, description="", priority="normal")
        return task.id


async def get_task(task_id: str):
    """从 DB 获取任务"""
    async with SessionLocal() as db:
        svc = TaskService(db)
        return await svc.get_by_id(task_id)


# ── 辅助 ───────────────────────────────────────────────────────────────────

def make_bus() -> EventBus:
    return EventBus()


async def start_worker(worker) -> asyncio.Task:
    task = asyncio.create_task(worker.start())
    await asyncio.sleep(0)
    return task


async def stop_worker(worker, task: asyncio.Task) -> None:
    await worker.stop()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ── 测试 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_output_written_to_progress_log():
    """成功执行后，agent 输出应写入 task.progress_log"""
    bus = make_bus()
    worker = DispatchWorker()
    worker.bus = bus

    bus.subscribe(TOPIC_AGENT_THOUGHTS)
    bus.subscribe(TOPIC_AGENT_HEARTBEAT)

    task_id = await create_test_task("进度回写测试战团")

    wt = await start_worker(worker)
    try:
        await bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id="trace-prog-01",
            event_type="task.dispatch.request",
            producer="orchestrator",
            payload={
                "task_id": task_id,
                "synapse": "overmind",
                "message": "请处理此任务",
            },
        )

        # 等待 dispatcher 处理完成（包括 DB 回写）
        await asyncio.sleep(0.5)

        task = await get_task(task_id)
        progress = task.progress_log or []
        assert len(progress) >= 1, "progress_log 应至少有一条记录"
        latest = progress[-1]
        assert "synapse.overmind" == latest["agent"], f"agent 应为 synapse.overmind，实际：{latest['agent']}"
        assert latest["content"], "content 不应为空"
    finally:
        await stop_worker(worker, wt)


@pytest.mark.asyncio
async def test_mock_output_content_in_progress_log():
    """mock 模式的输出内容应包含 [mock] 标记"""
    bus = make_bus()
    worker = DispatchWorker()
    worker.bus = bus

    bus.subscribe(TOPIC_AGENT_THOUGHTS)
    bus.subscribe(TOPIC_AGENT_HEARTBEAT)

    task_id = await create_test_task("mock输出测试")

    wt = await start_worker(worker)
    try:
        await bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id="trace-prog-02",
            event_type="task.dispatch.request",
            producer="orchestrator",
            payload={
                "task_id": task_id,
                "synapse": "code-expert",
                "message": "实现核心功能",
            },
        )

        await asyncio.sleep(0.5)

        task = await get_task(task_id)
        progress = task.progress_log or []
        assert len(progress) >= 1
        content = progress[-1]["content"]
        assert "[mock]" in content, f"mock 模式输出应含 [mock] 标记，实际：{content!r}"
        assert "code-expert" in content, f"输出应含 synapse 名称，实际：{content!r}"
    finally:
        await stop_worker(worker, wt)


@pytest.mark.asyncio
async def test_nonexistent_task_id_skipped_gracefully():
    """不存在的 task_id 不应导致 worker 崩溃"""
    bus = make_bus()
    worker = DispatchWorker()
    worker.bus = bus

    thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
    bus.subscribe(TOPIC_AGENT_HEARTBEAT)

    wt = await start_worker(worker)
    try:
        await bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id="trace-prog-03",
            event_type="task.dispatch.request",
            producer="orchestrator",
            payload={
                "task_id": "BT-NOT-EXIST",
                "synapse": "overmind",
                "message": "test",
            },
        )

        # agent.thoughts 仍然发出（worker 未崩溃）
        event = await asyncio.wait_for(thoughts_q.get(), timeout=3.0)
        assert event.payload["task_id"] == "BT-NOT-EXIST"
        assert worker.running, "worker 不应因 TaskNotFoundError 崩溃"
    finally:
        await stop_worker(worker, wt)


@pytest.mark.asyncio
async def test_multiple_dispatches_append_progress():
    """同一任务被多次 dispatch，progress_log 应累积追加"""
    bus = make_bus()
    worker = DispatchWorker()
    worker.bus = bus

    bus.subscribe(TOPIC_AGENT_THOUGHTS)
    bus.subscribe(TOPIC_AGENT_HEARTBEAT)

    task_id = await create_test_task("多次派发测试")

    wt = await start_worker(worker)
    try:
        for i in range(3):
            await bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id=f"trace-multi-{i}",
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={
                    "task_id": task_id,
                    "synapse": "overmind",
                    "message": f"第{i+1}次处理",
                },
            )

        # 等待所有三次处理完成
        await asyncio.sleep(1.0)

        task = await get_task(task_id)
        progress = task.progress_log or []
        assert len(progress) >= 3, f"应有至少 3 条进度记录，实际：{len(progress)}"
    finally:
        await stop_worker(worker, wt)


@pytest.mark.asyncio
async def test_empty_task_id_no_db_call():
    """空 task_id 不应触发 DB 操作，agent.thoughts 正常发出"""
    bus = make_bus()
    worker = DispatchWorker()
    worker.bus = bus

    thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
    bus.subscribe(TOPIC_AGENT_HEARTBEAT)

    wt = await start_worker(worker)
    try:
        await bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id="trace-empty-tid",
            event_type="task.dispatch.request",
            producer="orchestrator",
            payload={
                "task_id": "",   # 空 task_id
                "synapse": "overmind",
                "message": "无任务ID测试",
            },
        )

        # thoughts 应正常发出，worker 未崩溃
        event = await asyncio.wait_for(thoughts_q.get(), timeout=3.0)
        assert event.topic == TOPIC_AGENT_THOUGHTS
        assert worker.running
    finally:
        await stop_worker(worker, wt)
