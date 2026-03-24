"""Mission API —— chat-first 网页任务入口"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from greyfield_hive.db import SessionLocal, get_db
from greyfield_hive.models.task import TaskState
from greyfield_hive.services.execution_events import publish_stage_event
from greyfield_hive.services.event_bus import get_event_bus
from greyfield_hive.services.mode_router import ModeRouter
from greyfield_hive.services.task_service import TaskService
from greyfield_hive.api.tasks import _task_to_dict

router = APIRouter(prefix="/api/missions", tags=["missions"])


async def _launch_explicit_mode(task_id: str, trace_id: str) -> None:
    async with SessionLocal() as db:
        router = ModeRouter(db)
        await router.route(task_id, trace_id)


class MissionSwarmUnit(BaseModel):
    synapse: str
    message: str
    domain: str = ""


class MissionRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"
    creator: str = "user"
    mode: Literal["auto", "solo", "trial", "chain", "swarm"] = "auto"
    trial_candidates: list[str] = Field(default_factory=list)
    chain_stages: list[str] = Field(default_factory=list)
    swarm_units: list[MissionSwarmUnit] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode_shape(self) -> "MissionRequest":
        if self.mode == "trial" and len(self.trial_candidates) != 2:
            raise ValueError("trial 模式必须提供两个 trial_candidates")
        if self.mode == "chain" and len(self.chain_stages) < 2:
            raise ValueError("chain 模式至少需要两个 chain_stages")
        if self.mode == "swarm" and not self.swarm_units:
            raise ValueError("swarm 模式至少需要一个 swarm_units")
        return self


@router.post("", status_code=201)
async def submit_mission(body: MissionRequest, db=Depends(get_db)):
    svc = TaskService(db)
    meta: dict = {"skip_consolidation": True}
    explicit_mode = body.mode != "auto"
    if explicit_mode:
        meta["mode_source"] = "user"
        if body.mode == "trial":
            meta["trial_candidates"] = list(body.trial_candidates)
        elif body.mode == "chain":
            meta["chain_stages"] = list(body.chain_stages)
        elif body.mode == "swarm":
            meta["swarm_units"] = [unit.model_dump() for unit in body.swarm_units]

    task = await svc.create_task(
        title=body.title,
        description=body.description,
        priority=body.priority,
        creator=body.creator,
        meta=meta,
    )

    bus = get_event_bus()
    await publish_stage_event(
        bus,
        trace_id=task.trace_id,
        producer="mission-api",
        event_type="task.submitted",
        task_id=task.id,
        stage="mission",
        payload={"mode": body.mode, "title": body.title},
    )

    if explicit_mode:
        task = await svc.update_exec_mode(task.id, body.mode)
        await publish_stage_event(
            bus,
            trace_id=task.trace_id,
            producer="mission-api",
            event_type="task.mode.selected",
            task_id=task.id,
            stage="routing",
            payload={"mode": body.mode, "source": "user"},
        )
        task.state = TaskState.Spawning
        task.updated_at = datetime.now(timezone.utc)
        task.append_flow(TaskState.Incubating.value, TaskState.Planning.value, "mission-api", "显式模式任务，跳过主脑分析")
        task.append_flow(TaskState.Planning.value, TaskState.Reviewing.value, "mission-api", "显式模式任务，直接进入执行前检查")
        task.append_flow(TaskState.Reviewing.value, TaskState.Spawning.value, "mission-api", "显式模式任务，后台启动 ModeRouter")
        await db.commit()
        await db.refresh(task)
        asyncio.create_task(_launch_explicit_mode(task.id, task.trace_id))

    return {
        "task": _task_to_dict(task),
        "run": {
            "started": True,
            "entrypoint": "task.created",
            "mode": body.mode,
        },
    }
