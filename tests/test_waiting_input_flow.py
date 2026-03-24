import json

import pytest

from greyfield_hive.agents.overmind_agent import OvermindAgent
from greyfield_hive.db import Base, SessionLocal, engine
from greyfield_hive.models.task import TaskState
from greyfield_hive.services.event_bus import BusEvent, EventBus, TOPIC_TASK_DISPATCH
from greyfield_hive.services.task_service import TaskService
from greyfield_hive.workers.dispatcher import DispatchWorker


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


class _StaticAdapter:
    def __init__(self, result: dict) -> None:
        self._result = result

    async def invoke(self, synapse: str, message: str, env: dict, timeout: int) -> dict:
        return dict(self._result)


@pytest.mark.asyncio
async def test_overmind_blockers_set_waiting_input_state():
    async with SessionLocal() as db:
        task = await TaskService(db).create_task(title="爬一下今天天气")

    worker = DispatchWorker()
    worker.bus = EventBus()
    worker._adapter = _StaticAdapter(
        {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "summary": "缺少地点，无法执行天气抓取。",
                    "domain": "general",
                    "todos": ["确认地点"],
                    "risks": ["地点不明确会导致结果无效"],
                    "blockers": ["未指定查询地点"],
                    "recommended_state": "Planning",
                    "exec_mode": "solo",
                },
                ensure_ascii=False,
            ),
            "stderr": "",
        }
    )

    await worker._dispatch(
        BusEvent(
            trace_id="trace-waiting",
            topic=TOPIC_TASK_DISPATCH,
            event_type="task.dispatch.request",
            producer="test",
            payload={
                "task_id": task.id,
                "synapse": "overmind",
                "message": "爬一下今天天气",
                "next_state": TaskState.Planning.value,
            },
        )
    )

    async with SessionLocal() as db:
        refreshed = await TaskService(db).get_by_id(task.id)

    assert refreshed.state == TaskState.WaitingInput
    assert refreshed.meta["awaiting_user_input"] is True
    assert refreshed.meta["analysis_blockers"] == ["未指定查询地点"]
    assert refreshed.meta["recommended_state"] == TaskState.WaitingInput.value


@pytest.mark.asyncio
async def test_dispatch_failure_falls_back_to_dormant():
    async with SessionLocal() as db:
        task = await TaskService(db).create_task(title="失败任务")

    worker = DispatchWorker()
    worker.bus = EventBus()
    worker._adapter = _StaticAdapter(
        {
            "returncode": -1,
            "stdout": "",
            "stderr": "simulated failure",
        }
    )

    await worker._dispatch(
        BusEvent(
            trace_id="trace-fail",
            topic=TOPIC_TASK_DISPATCH,
            event_type="task.dispatch.request",
            producer="test",
            payload={
                "task_id": task.id,
                "synapse": "overmind",
                "message": "失败任务",
                "next_state": TaskState.Planning.value,
            },
        )
    )

    async with SessionLocal() as db:
        refreshed = await TaskService(db).get_by_id(task.id)

    assert refreshed.state == TaskState.Dormant


def test_parse_response_recognizes_blockers():
    agent = OvermindAgent(client=None)
    result = agent._parse_response(
        json.dumps(
            {
                "summary": "先补充地点。",
                "domain": "general",
                "todos": ["确认地点"],
                "risks": ["地点不明确会导致结果无效"],
                "blockers": ["未指定查询地点"],
                "recommended_status": "Planning",
                "exec_mode": "solo",
            },
            ensure_ascii=False,
        )
    )

    assert result.blockers == ["未指定查询地点"]
    assert result.recommended_state == "WaitingInput"
