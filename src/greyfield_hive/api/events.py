"""事件查询 API —— 提供全量审计链查询 + SSE 实时流

GET /api/events              历史事件列表（分页）
GET /api/events/stream       SSE 实时事件流（keep-alive）
"""

import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc

from greyfield_hive.db import get_db
from greyfield_hive.models.event import HiveEvent
from greyfield_hive.services.event_bus import get_event_bus, BusEvent

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_to_dict(ev: HiveEvent) -> dict:
    return {
        "event_id":   ev.id,       # 与 WS BusEvent.event_id 对齐
        "trace_id":   ev.trace_id,
        "task_id":    ev.task_id,
        "topic":      ev.topic,
        "event_type": ev.event_type,
        "producer":   ev.producer,
        "payload":    ev.payload,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


@router.get("")
async def list_events(
    trace_id: Optional[str] = Query(None),
    task_id:  Optional[str] = Query(None),
    topic:    Optional[str] = Query(None),
    limit:    int = Query(100, ge=1, le=500),
    offset:   int = Query(0, ge=0),
    db=Depends(get_db),
):
    q = select(HiveEvent).order_by(desc(HiveEvent.created_at)).limit(limit).offset(offset)
    if trace_id:
        q = q.where(HiveEvent.trace_id == trace_id)
    if task_id:
        q = q.where(HiveEvent.task_id == task_id)
    if topic:
        q = q.where(HiveEvent.topic == topic)
    result = await db.execute(q)
    events = result.scalars().all()
    return [_event_to_dict(ev) for ev in events]


# ── SSE 实时事件流 ────────────────────────────────────────────────────────────

@router.get("/stream")
async def stream_events(
    topic:   Optional[str] = Query(None, description="只推送指定 topic，如 task.status"),
    task_id: Optional[str] = Query(None, description="只推送指定任务的事件"),
):
    """
    SSE 实时事件流。客户端保持长连接，虫巢每产生事件即推送。

    - `topic`   可选过滤，如 `task.status`、`task.completed`
    - `task_id` 可选过滤，只关注某个任务的事件

    事件格式（text/event-stream）：
    ```
    data: {"topic": "...", "event_type": "...", "task_id": "...", "payload": {...}}

    ```
    """
    bus = get_event_bus()
    q: asyncio.Queue = asyncio.Queue()

    async def _callback(ev: BusEvent) -> None:
        # 过滤
        if topic and ev.topic != topic:
            return
        if task_id and ev.payload.get("task_id") != task_id:
            return
        await q.put(ev)

    bus.register_ws_callback(_callback)

    async def _generator():
        try:
            # 发送初始连接确认
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    ev: BusEvent = await asyncio.wait_for(q.get(), timeout=20.0)
                    data = json.dumps({
                        "event_id":   ev.event_id,
                        "trace_id":   ev.trace_id,
                        "topic":      ev.topic,
                        "event_type": ev.event_type,
                        "producer":   ev.producer,
                        "payload":    ev.payload,
                        "created_at": ev.created_at,
                    }, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # keep-alive 心跳（避免代理/负载均衡断连）
                    yield ": keep-alive\n\n"
        finally:
            bus.unregister_ws_callback(_callback)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
