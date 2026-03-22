"""事件查询 API —— 提供全量审计链查询"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc

from greyfield_hive.db import get_db
from greyfield_hive.models.event import HiveEvent

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_to_dict(ev: HiveEvent) -> dict:
    return {
        "id":         ev.id,
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
