"""虫巢事件总线 —— 基于 asyncio.Queue，支持多消费者组

设计原则：不依赖 Redis，单进程内可靠传递。
Tier 3+ 可升级为 Redis Streams（接口不变）。
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field

from loguru import logger


# ── 标准 Topic ──────────────────────────────────────────
TOPIC_TASK_CREATED   = "task.created"
TOPIC_TASK_STATUS    = "task.status"
TOPIC_TASK_DISPATCH  = "task.dispatch"
TOPIC_TASK_COMPLETED = "task.completed"
TOPIC_TASK_STALLED   = "task.stalled"
TOPIC_AGENT_THOUGHTS = "agent.thoughts"
TOPIC_AGENT_HEARTBEAT = "agent.heartbeat"
TOPIC_AGENT_TODO_UPDATE = "agent.todo.update"
TOPIC_TASK_DELETED   = "task.deleted"


@dataclass
class BusEvent:
    event_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id:   str = ""
    topic:      str = ""
    event_type: str = ""
    producer:   str = ""
    payload:    dict = field(default_factory=dict)
    meta:       dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── 事件总线 ─────────────────────────────────────────────

class EventBus:
    """进程内事件总线 —— asyncio.Queue + 广播订阅"""

    def __init__(self) -> None:
        # topic → list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        # WebSocket 广播回调
        self._ws_callbacks: list[Callable[[BusEvent], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    async def publish(
        self,
        topic: str,
        trace_id: str,
        event_type: str,
        producer: str,
        payload: dict | None = None,
        meta: dict | None = None,
    ) -> BusEvent:
        event = BusEvent(
            trace_id=trace_id,
            topic=topic,
            event_type=event_type,
            producer=producer,
            payload=payload or {},
            meta=meta or {},
        )
        logger.debug(f"[EventBus] publish {topic}/{event_type} producer={producer} trace={trace_id[:8]}")

        async with self._lock:
            queues = list(self._subscribers.get(topic, []))

        for q in queues:
            await q.put(event)

        # WS 广播（不阻塞总线）
        for cb in self._ws_callbacks:
            asyncio.create_task(cb(event))

        return event

    def subscribe(self, topic: str) -> asyncio.Queue:
        """注册订阅，返回专属 Queue"""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(topic, []).append(q)
        logger.debug(f"[EventBus] subscribe {topic}")
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(topic, [])
        if q in subs:
            subs.remove(q)

    def register_ws_callback(self, cb: Callable[[BusEvent], Awaitable[None]]) -> None:
        self._ws_callbacks.append(cb)

    def unregister_ws_callback(self, cb: Callable[[BusEvent], Awaitable[None]]) -> None:
        if cb in self._ws_callbacks:
            self._ws_callbacks.remove(cb)


# ── 单例 ──────────────────────────────────────────────────
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
