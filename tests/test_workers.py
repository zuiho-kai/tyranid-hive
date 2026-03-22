"""Worker 集成测试 —— OrchestratorWorker + DispatchWorker

策略：
- 每个测试构造一个独立的 EventBus 实例（绕过单例）
- create_task 后 await asyncio.sleep(0) 让 worker 完成订阅
- Worker 在 asyncio.Task 中运行，测试结束后 cancel
"""

import asyncio
import pytest

from greyfield_hive.services.event_bus import (
    EventBus,
    BusEvent,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_STALLED,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_DISPATCH,
    TOPIC_AGENT_HEARTBEAT,
    TOPIC_AGENT_THOUGHTS,
)
from greyfield_hive.models.task import TaskState
from greyfield_hive.workers.orchestrator import OrchestratorWorker
from greyfield_hive.workers.dispatcher import DispatchWorker
from greyfield_hive.adapters.openclaw import MockAdapter


# ── 辅助函数 ────────────────────────────────────────────────────────

async def wait_for_event(q: asyncio.Queue, timeout: float = 2.0) -> BusEvent:
    """等待队列中的下一个事件，超时则抛出 TimeoutError"""
    return await asyncio.wait_for(q.get(), timeout=timeout)


def make_bus() -> EventBus:
    """创建一个干净的 EventBus 实例（不污染单例）"""
    return EventBus()


async def start_worker(worker) -> asyncio.Task:
    """启动 worker 并等待其完成订阅"""
    task = asyncio.create_task(worker.start())
    await asyncio.sleep(0)  # 让 worker 运行到第一个 await，完成订阅
    return task


async def stop_worker(worker, task: asyncio.Task) -> None:
    """停止 worker 并清理 task"""
    await worker.stop()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ── OrchestratorWorker 测试 ──────────────────────────────────────────

class TestOrchestratorWorker:

    @pytest.mark.asyncio
    async def test_task_created_dispatches_to_overmind(self):
        """task.created → 应发布 task.dispatch，synapse=overmind"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_CREATED,
                trace_id="trace-001",
                event_type="task.created",
                producer="test",
                payload={"task_id": "BT-001", "title": "测试战团"},
            )

            event = await wait_for_event(dispatch_q)
            assert event.topic == TOPIC_TASK_DISPATCH
            assert event.payload["task_id"] == "BT-001"
            assert event.payload["synapse"] == "overmind"
            assert event.payload["next_state"] == TaskState.Planning.value
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_task_status_with_synapse_mapping_dispatches(self):
        """task.status → Consolidating 有映射 → 应发布 task.dispatch，synapse=evolution-master"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_STATUS,
                trace_id="trace-002",
                event_type="task.status.changed",
                producer="test",
                payload={
                    "task_id": "BT-002",
                    "from": "Executing",
                    "to": TaskState.Consolidating.value,
                },
            )

            event = await wait_for_event(dispatch_q)
            assert event.payload["synapse"] == "evolution-master"
            assert event.payload["task_id"] == "BT-002"
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_task_status_executing_no_dispatch(self):
        """task.status → Executing 无 synapse 映射 → 不应发布 task.dispatch"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_STATUS,
                trace_id="trace-003",
                event_type="task.status.changed",
                producer="test",
                payload={
                    "task_id": "BT-003",
                    "from": "Spawning",
                    "to": TaskState.Executing.value,
                },
            )

            # 短暂等待，确认没有 dispatch 事件
            await asyncio.sleep(0.3)
            assert dispatch_q.empty(), "Executing 状态不应触发 dispatch"
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_task_stalled_dispatches_to_overmind(self):
        """task.stalled → 应发布 task.dispatch，synapse=overmind，next_state=Dormant"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_STALLED,
                trace_id="trace-004",
                event_type="task.stalled",
                producer="test",
                payload={"task_id": "BT-004"},
            )

            event = await wait_for_event(dispatch_q)
            assert event.payload["synapse"] == "overmind"
            assert event.payload["next_state"] == TaskState.Dormant.value
            assert event.payload["task_id"] == "BT-004"
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_task_completed_no_dispatch(self):
        """task.completed → 不应发布任何 task.dispatch"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_COMPLETED,
                trace_id="trace-005",
                event_type="task.completed",
                producer="test",
                payload={"task_id": "BT-005"},
            )

            await asyncio.sleep(0.3)
            assert dispatch_q.empty(), "Completed 事件不应触发 dispatch"
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_task_status_unknown_state_ignored(self):
        """task.status → 未知状态 → 应安全忽略，不 dispatch"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_STATUS,
                trace_id="trace-006",
                event_type="task.status.changed",
                producer="test",
                payload={"task_id": "BT-006", "to": "InvalidState"},
            )

            await asyncio.sleep(0.3)
            assert dispatch_q.empty(), "未知状态不应触发 dispatch"
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_running_property(self):
        """running 属性应在 start 后为 True，stop 后为 False"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        assert not worker.running

        task = await start_worker(worker)
        assert worker.running

        await stop_worker(worker, task)
        assert not worker.running

    @pytest.mark.asyncio
    async def test_multiple_events_processed_in_order(self):
        """连续发布多个 task.created → 应全部触发 dispatch"""
        bus = make_bus()
        worker = OrchestratorWorker()
        worker.bus = bus

        dispatch_q = bus.subscribe(TOPIC_TASK_DISPATCH)
        task = await start_worker(worker)
        try:
            for i in range(3):
                await bus.publish(
                    topic=TOPIC_TASK_CREATED,
                    trace_id=f"trace-{i:03d}",
                    event_type="task.created",
                    producer="test",
                    payload={"task_id": f"BT-{i:03d}", "title": f"战团{i}"},
                )

            events = []
            for _ in range(3):
                e = await wait_for_event(dispatch_q)
                events.append(e)

            task_ids = {e.payload["task_id"] for e in events}
            assert task_ids == {"BT-000", "BT-001", "BT-002"}
        finally:
            await stop_worker(worker, task)


# ── DispatchWorker 测试 ──────────────────────────────────────────────

class TestDispatchWorker:

    @pytest.mark.asyncio
    async def test_dispatch_publishes_heartbeat_and_thoughts(self):
        """task.dispatch → 应发布 agent.heartbeat + agent.thoughts"""
        bus = make_bus()
        worker = DispatchWorker(max_concurrent=2)
        worker.bus = bus

        heartbeat_q = bus.subscribe(TOPIC_AGENT_HEARTBEAT)
        thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id="trace-d01",
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={
                    "task_id": "BT-D01",
                    "synapse": "overmind",
                    "message": "请处理此任务",
                    "next_state": "Planning",
                },
            )

            heartbeat = await wait_for_event(heartbeat_q)
            assert heartbeat.event_type == "agent.dispatch.start"
            assert heartbeat.payload["task_id"] == "BT-D01"
            assert heartbeat.payload["synapse"] == "overmind"

            thoughts = await wait_for_event(thoughts_q, timeout=5.0)
            assert thoughts.topic == TOPIC_AGENT_THOUGHTS
            assert thoughts.payload["task_id"] == "BT-D01"
            assert thoughts.payload["synapse"] == "overmind"
            assert "output" in thoughts.payload
            assert "return_code" in thoughts.payload
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_dispatch_mock_mode_when_openclaw_unavailable(self):
        """openclaw 不存在时应使用 mock 模式，return_code=0"""
        bus = make_bus()
        worker = DispatchWorker()
        worker.bus = bus
        worker._adapter = MockAdapter()  # 强制 mock，不依赖 CLI 探测

        thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
        bus.subscribe(TOPIC_AGENT_HEARTBEAT)  # 消耗 heartbeat
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id="trace-d02",
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={
                    "task_id": "BT-D02",
                    "synapse": "code-expert",
                    "message": "实现功能X",
                },
            )

            thoughts = await wait_for_event(thoughts_q, timeout=5.0)
            assert thoughts.payload["return_code"] == 0
            assert "[mock]" in thoughts.payload["output"]
            assert "code-expert" in thoughts.payload["output"]
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_dispatch_trace_id_propagated(self):
        """trace_id 应从 dispatch 事件传播到 thoughts 事件"""
        bus = make_bus()
        worker = DispatchWorker()
        worker.bus = bus

        thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
        bus.subscribe(TOPIC_AGENT_HEARTBEAT)
        task = await start_worker(worker)
        try:
            trace = "trace-propagate-xyz"
            await bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id=trace,
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={"task_id": "BT-D03", "synapse": "overmind", "message": "test"},
            )

            thoughts = await wait_for_event(thoughts_q, timeout=5.0)
            assert thoughts.trace_id == trace
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_dispatch_concurrency_semaphore(self):
        """max_concurrent=1 时，并发 dispatch 应串行执行，两个都最终完成"""
        bus = make_bus()
        worker = DispatchWorker(max_concurrent=1)
        worker.bus = bus

        thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
        bus.subscribe(TOPIC_AGENT_HEARTBEAT)
        task = await start_worker(worker)
        try:
            for i in range(2):
                await bus.publish(
                    topic=TOPIC_TASK_DISPATCH,
                    trace_id=f"trace-conc-{i}",
                    event_type="task.dispatch.request",
                    producer="orchestrator",
                    payload={"task_id": f"BT-C0{i}", "synapse": "overmind", "message": "test"},
                )

            results = []
            for _ in range(2):
                e = await wait_for_event(thoughts_q, timeout=5.0)
                results.append(e)

            task_ids = {e.payload["task_id"] for e in results}
            assert task_ids == {"BT-C00", "BT-C01"}
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_dispatch_producer_set_correctly(self):
        """thoughts 事件的 producer 应为 synapse.{synapse_name}"""
        bus = make_bus()
        worker = DispatchWorker()
        worker.bus = bus

        thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
        bus.subscribe(TOPIC_AGENT_HEARTBEAT)
        task = await start_worker(worker)
        try:
            await bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id="trace-d05",
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={"task_id": "BT-D05", "synapse": "evolution-master", "message": "test"},
            )

            thoughts = await wait_for_event(thoughts_q, timeout=5.0)
            assert thoughts.producer == "synapse.evolution-master"
        finally:
            await stop_worker(worker, task)

    @pytest.mark.asyncio
    async def test_running_property(self):
        """running 属性应在 start 后为 True，stop 后为 False"""
        bus = make_bus()
        worker = DispatchWorker()
        worker.bus = bus

        assert not worker.running

        task = await start_worker(worker)
        assert worker.running

        await stop_worker(worker, task)
        assert not worker.running


# ── 端到端集成：Orchestrator → Dispatcher ────────────────────────────

class TestOrchestratorDispatcherIntegration:

    @pytest.mark.asyncio
    async def test_task_created_flows_to_agent_thoughts(self):
        """task.created → Orchestrator → Dispatcher → agent.thoughts 完整链路"""
        bus = make_bus()

        orchestrator = OrchestratorWorker()
        orchestrator.bus = bus

        dispatcher = DispatchWorker()
        dispatcher.bus = bus
        dispatcher._adapter = MockAdapter()  # 强制 mock，不依赖 CLI 探测

        thoughts_q = bus.subscribe(TOPIC_AGENT_THOUGHTS)
        bus.subscribe(TOPIC_AGENT_HEARTBEAT)

        orch_task = await start_worker(orchestrator)
        disp_task = await start_worker(dispatcher)
        try:
            await bus.publish(
                topic=TOPIC_TASK_CREATED,
                trace_id="trace-e2e-001",
                event_type="task.created",
                producer="api",
                payload={"task_id": "BT-E2E-001", "title": "端到端测试战团"},
            )

            thoughts = await wait_for_event(thoughts_q, timeout=5.0)
            assert thoughts.payload["task_id"] == "BT-E2E-001"
            assert thoughts.payload["synapse"] == "overmind"
            assert thoughts.payload["return_code"] == 0
        finally:
            await stop_worker(orchestrator, orch_task)
            await stop_worker(dispatcher, disp_task)
