"""停滞任务检测器测试"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from greyfield_hive.db import engine, Base, SessionLocal
from greyfield_hive.models.task import Task, TaskState
from greyfield_hive.services.task_service import TaskService
from greyfield_hive.workers.stall_detector import StallDetector
from greyfield_hive.services.event_bus import get_event_bus, TOPIC_TASK_STALLED


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def reset_event_bus():
    """清空事件总线订阅，避免跨测试污染"""
    bus = get_event_bus()
    bus._subscribers.clear()
    yield


async def _make_stale_task(title: str, state: TaskState, age_seconds: int) -> Task:
    """创建一个 updated_at 已在过去的任务"""
    async with SessionLocal() as db:
        svc = TaskService(db)
        task = await svc.create_task(title=title)
        task_id = task.id

    # 手动回拨 updated_at
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    async with SessionLocal() as db:
        await db.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(state=state, updated_at=stale_time)
        )
        await db.commit()

    async with SessionLocal() as db:
        svc = TaskService(db)
        return await svc.get_by_id(task_id)


# ── _scan 核心逻辑 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_emits_stalled_event_for_old_task():
    """超时任务应触发 task.stalled 事件"""
    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_STALLED)

    await _make_stale_task("停滞任务", TaskState.Executing, age_seconds=7200)

    detector = StallDetector(stall_seconds=3600, check_interval=9999)
    await detector._scan()

    try:
        event = q.get_nowait()
        assert event.event_type == "task.stalled"
        assert event.payload["stall_secs"] == 3600
    except asyncio.QueueEmpty:
        pytest.fail("未收到 task.stalled 事件")


@pytest.mark.asyncio
async def test_scan_does_not_emit_for_fresh_task():
    """未超时任务不应触发告警"""
    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_STALLED)

    await _make_stale_task("新鲜任务", TaskState.Executing, age_seconds=10)

    detector = StallDetector(stall_seconds=3600, check_interval=9999)
    await detector._scan()

    assert q.empty()


@pytest.mark.asyncio
async def test_scan_skips_terminal_tasks():
    """终态任务（Complete/Cancelled）不应被检测"""
    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_STALLED)

    await _make_stale_task("完成任务", TaskState.Complete, age_seconds=7200)
    await _make_stale_task("取消任务", TaskState.Cancelled, age_seconds=7200)

    detector = StallDetector(stall_seconds=3600, check_interval=9999)
    await detector._scan()

    assert q.empty()


@pytest.mark.asyncio
async def test_scan_no_duplicate_alerts():
    """同一任务不重复告警（_alerted 集合去重）"""
    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_STALLED)

    await _make_stale_task("重复告警任务", TaskState.Planning, age_seconds=7200)

    detector = StallDetector(stall_seconds=3600, check_interval=9999)
    await detector._scan()
    await detector._scan()   # 第二次扫描

    # 只应收到一个事件
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    assert len(events) == 1


@pytest.mark.asyncio
async def test_clear_alert_allows_re_alert():
    """clear_alert 后，同一任务可以再次触发告警"""
    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_STALLED)

    task = await _make_stale_task("重置告警任务", TaskState.Planning, age_seconds=7200)

    detector = StallDetector(stall_seconds=3600, check_interval=9999)
    await detector._scan()   # 第一次 → 告警
    detector.clear_alert(task.id)
    await detector._scan()   # 第二次 → 再次告警

    events = []
    while not q.empty():
        events.append(q.get_nowait())
    assert len(events) == 2


@pytest.mark.asyncio
async def test_scan_multiple_stalled_tasks():
    """多个停滞任务都应触发告警"""
    bus = get_event_bus()
    q = bus.subscribe(TOPIC_TASK_STALLED)

    await _make_stale_task("停滞1", TaskState.Executing, age_seconds=7200)
    await _make_stale_task("停滞2", TaskState.Planning,  age_seconds=7200)
    await _make_stale_task("停滞3", TaskState.Reviewing, age_seconds=7200)

    detector = StallDetector(stall_seconds=3600, check_interval=9999)
    await detector._scan()

    events = []
    while not q.empty():
        events.append(q.get_nowait())
    assert len(events) == 3


# ── start/stop 生命周期 ───────────────────────────────────

@pytest.mark.asyncio
async def test_detector_start_stop():
    """启动后 running=True，stop 后 running=False"""
    detector = StallDetector(stall_seconds=3600, check_interval=0.05)
    assert not detector.running

    task = asyncio.create_task(detector.start())
    await asyncio.sleep(0.1)
    assert detector.running

    await detector.stop()
    task.cancel()
    assert not detector.running
