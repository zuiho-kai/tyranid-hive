"""事件总线测试"""

import asyncio
import pytest
from greyfield_hive.services.event_bus import EventBus, TOPIC_TASK_CREATED


@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    q = bus.subscribe(TOPIC_TASK_CREATED)

    event = await bus.publish(
        topic=TOPIC_TASK_CREATED,
        trace_id="test-trace",
        event_type="task.created",
        producer="test",
        payload={"task_id": "T-001"},
    )

    assert not q.empty()
    received = q.get_nowait()
    assert received.topic == TOPIC_TASK_CREATED
    assert received.payload["task_id"] == "T-001"


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    q1 = bus.subscribe(TOPIC_TASK_CREATED)
    q2 = bus.subscribe(TOPIC_TASK_CREATED)

    await bus.publish(
        topic=TOPIC_TASK_CREATED,
        trace_id="t",
        event_type="task.created",
        producer="test",
        payload={},
    )

    assert not q1.empty()
    assert not q2.empty()


@pytest.mark.asyncio
async def test_ws_callback():
    bus = EventBus()
    received = []

    async def cb(event):
        received.append(event)

    bus.register_ws_callback(cb)
    await bus.publish(
        topic=TOPIC_TASK_CREATED,
        trace_id="t",
        event_type="task.created",
        producer="test",
        payload={},
    )
    await asyncio.sleep(0.05)
    assert len(received) == 1
