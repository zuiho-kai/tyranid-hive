"""虫巢 API 服务入口 —— FastAPI + 后台 Worker"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from greyfield_hive.middleware import RequestLoggingMiddleware

_STATIC_DIR = Path(__file__).parent / "static"

from greyfield_hive.db import init_db
from greyfield_hive.services.event_bus import get_event_bus
from greyfield_hive.workers.orchestrator import OrchestratorWorker
from greyfield_hive.workers.dispatcher import DispatchWorker
from greyfield_hive.api.tasks import router as tasks_router
from greyfield_hive.api.units import router as units_router
from greyfield_hive.api.events import router as events_router
from greyfield_hive.api.lessons import router as lessons_router
from greyfield_hive.api.playbooks import router as playbooks_router
from greyfield_hive.api.stats import router as stats_router
from greyfield_hive.api.ws import router as ws_router, register_ws_broadcast


_orchestrator: OrchestratorWorker | None = None
_dispatcher:   DispatchWorker | None     = None
_bg_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator, _dispatcher

    # 1. 初始化数据库
    await init_db()
    logger.info("✅ 数据库初始化完成")

    # 2. 注册 WebSocket 广播
    register_ws_broadcast()

    # 3. 启动后台 Worker
    _orchestrator = OrchestratorWorker()
    _dispatcher   = DispatchWorker(max_concurrent=3)

    _bg_tasks.append(asyncio.create_task(_orchestrator.start(), name="orchestrator"))
    _bg_tasks.append(asyncio.create_task(_dispatcher.start(),   name="dispatcher"))
    logger.info("✅ 编排器 + 派发器已启动")

    yield

    # 清理
    if _orchestrator:
        await _orchestrator.stop()
    if _dispatcher:
        await _dispatcher.stop()
    for t in _bg_tasks:
        t.cancel()
    logger.info("👋 虫巢关闭")


app = FastAPI(
    title="Tyranid Hive",
    description="泰伦虫群多 Agent 编排框架 —— 事件驱动 · 基因进化 · 适存驱动",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# 注册路由
app.include_router(tasks_router)
app.include_router(units_router)
app.include_router(events_router)
app.include_router(lessons_router)
app.include_router(playbooks_router)
app.include_router(stats_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    from greyfield_hive.db import engine
    from sqlalchemy import text

    # DB 连通性探针
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    workers_ok = (
        _orchestrator is not None and _orchestrator.running
        and _dispatcher is not None and _dispatcher.running
    )

    status = "synapse_active" if (db_ok and workers_ok) else "degraded"
    return {
        "status":   status,
        "service":  "tyranid-hive",
        "version":  "0.1.0",
        "db":       "ok" if db_ok else "error",
        "workers":  "ok" if workers_ok else "stopped",
    }


@app.get("/")
async def root():
    # 有静态文件时直接返回 dashboard
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "hive": "Tyranid Hive",
        "docs": "/docs",
        "health": "/health",
        "tasks": "/api/tasks",
        "synapses": "/api/synapses",
        "events": "/api/events",
        "websocket": "/ws",
    }


# 静态资源（dashboard build 产物）
if _STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")
