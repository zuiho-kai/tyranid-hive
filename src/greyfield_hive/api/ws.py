"""WebSocket —— 实时推送事件流到前端"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from greyfield_hive.services.event_bus import get_event_bus, BusEvent

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"[WS] 新连接, 当前={len(self._connections)}")

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"[WS] 断开, 剩余={len(self._connections)}")

    async def broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def _bus_broadcast(event: BusEvent) -> None:
    await manager.broadcast({
        "event_id":   event.event_id,
        "trace_id":   event.trace_id,
        "topic":      event.topic,
        "event_type": event.event_type,
        "producer":   event.producer,
        "payload":    event.payload,
        "created_at": event.created_at,
    })


def register_ws_broadcast() -> None:
    """在应用启动时注册广播回调"""
    bus = get_event_bus()
    bus.register_ws_callback(_bus_broadcast)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # 保持连接，等待客户端 ping 或断开
            await asyncio.sleep(30)
            try:
                await ws.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
