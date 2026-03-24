from __future__ import annotations

from typing import Any

from greyfield_hive.services.event_bus import EventBus, TOPIC_TASK_STAGE


async def publish_stage_event(
    bus: EventBus,
    *,
    trace_id: str,
    producer: str,
    event_type: str,
    task_id: str,
    stage: str,
    payload: dict[str, Any] | None = None,
) -> None:
    body = {"task_id": task_id, "stage": stage}
    if payload:
        body.update(payload)
    await bus.publish(
        topic=TOPIC_TASK_STAGE,
        trace_id=trace_id,
        event_type=event_type,
        producer=producer,
        payload=body,
    )
