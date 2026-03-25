from __future__ import annotations

from typing import Any

from greyfield_hive.db import SessionLocal
from greyfield_hive.models.event import HiveEvent
from greyfield_hive.services.event_bus import EventBus, TOPIC_TASK_STAGE


async def publish_task_event(
    bus: EventBus,
    *,
    topic: str,
    trace_id: str,
    producer: str,
    event_type: str,
    task_id: str,
    payload: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    body = {"task_id": task_id}
    if payload:
        body.update(payload)

    async with SessionLocal() as db:
        db.add(
            HiveEvent(
                trace_id=trace_id,
                task_id=task_id,
                topic=topic,
                event_type=event_type,
                producer=producer,
                payload=body,
                meta=meta or {},
            )
        )
        await db.commit()

    await bus.publish(
        topic=topic,
        trace_id=trace_id,
        event_type=event_type,
        producer=producer,
        payload=body,
        meta=meta or {},
    )


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
    await publish_task_event(
        bus,
        topic=TOPIC_TASK_STAGE,
        trace_id=trace_id,
        event_type=event_type,
        producer=producer,
        task_id=task_id,
        payload=body,
    )
