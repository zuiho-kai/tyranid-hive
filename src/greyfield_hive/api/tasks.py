"""任务 REST API —— CRUD + 状态流转"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from greyfield_hive.db import get_db
from greyfield_hive.models.task import Task, TaskState
from greyfield_hive.services.task_service import TaskService, InvalidTransitionError, TaskNotFoundError

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Schemas ──────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    title:       str
    description: str = ""
    priority:    str = "normal"
    creator:     str = "user"
    assignee_synapse: Optional[str] = None
    meta:        dict = {}


class TransitionRequest(BaseModel):
    new_state: str
    agent:     str = "user"
    reason:    str = ""


class DispatchRequest(BaseModel):
    synapse:  str
    message:  str = ""


class ProgressRequest(BaseModel):
    agent:   str
    content: str


class TodosRequest(BaseModel):
    todos: list[dict]


class PatchTaskRequest(BaseModel):
    title:       Optional[str] = None
    description: Optional[str] = None
    priority:    Optional[str] = None


class BulkTransitionRequest(BaseModel):
    task_ids:  list[str]
    new_state: str
    agent:     str = "user"
    reason:    str = ""


class BulkDeleteRequest(BaseModel):
    task_ids: list[str]


class CleanupRequest(BaseModel):
    days: int = 30


def _task_to_dict(task: Task) -> dict:
    return {
        "id":               task.id,
        "task_uuid":        task.task_uuid,
        "trace_id":         task.trace_id,
        "title":            task.title,
        "description":      task.description,
        "state":            task.state.value if task.state else None,
        "priority":         task.priority,
        "exec_mode":        task.exec_mode.value if task.exec_mode else None,
        "assignee_synapse": task.assignee_synapse,
        "creator":          task.creator,
        "flow_log":         task.flow_log or [],
        "progress_log":     task.progress_log or [],
        "todos":            task.todos or [],
        "meta":             task.meta or {},
        "created_at":       task.created_at.isoformat() if task.created_at else None,
        "updated_at":       task.updated_at.isoformat() if task.updated_at else None,
    }


# ── 端点 ──────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_task(body: CreateTaskRequest, db=Depends(get_db)):
    svc = TaskService(db)
    task = await svc.create_task(
        title=body.title,
        description=body.description,
        priority=body.priority,
        creator=body.creator,
        assignee_synapse=body.assignee_synapse,
        meta=body.meta,
    )
    return _task_to_dict(task)


@router.get("")
async def list_tasks(
    state:    Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    q:        Optional[str] = Query(None, description="关键词搜索（title / description / id）"),
    limit:    int            = Query(50, ge=1, le=200),
    offset:   int            = Query(0, ge=0),
    db=Depends(get_db),
):
    svc = TaskService(db)
    state_enum = TaskState(state) if state else None
    tasks = await svc.list_tasks(
        state=state_enum, priority=priority, assignee=assignee, q=q,
        limit=limit, offset=offset,
    )
    return [_task_to_dict(t) for t in tasks]


@router.get("/stats")
async def task_stats(db=Depends(get_db)):
    """返回任务统计（各状态计数）"""
    svc = TaskService(db)
    return await svc.stats()


@router.post("/bulk/transition")
async def bulk_transition(body: BulkTransitionRequest, db=Depends(get_db)):
    """批量状态流转 —— 一次请求操作多个任务"""
    try:
        new_state = TaskState(body.new_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"未知状态: {body.new_state}")

    svc = TaskService(db)
    results = {"ok": [], "failed": []}
    for tid in body.task_ids:
        try:
            await svc.transition(tid, new_state, agent=body.agent, reason=body.reason)
            results["ok"].append(tid)
        except (TaskNotFoundError, InvalidTransitionError) as e:
            results["failed"].append({"id": tid, "reason": str(e)})
    return results


@router.delete("/bulk", status_code=200)
async def bulk_delete_tasks(body: BulkDeleteRequest, db=Depends(get_db)):
    """批量删除任务"""
    svc = TaskService(db)
    return await svc.bulk_delete(body.task_ids)


@router.delete("/cleanup", status_code=200)
async def cleanup_old_tasks(
    days: int = Query(30, ge=1, description="删除 N 天前完成/取消的任务"),
    db=Depends(get_db),
):
    """清理旧的已完成/已取消任务"""
    svc = TaskService(db)
    return await svc.delete_old_completed(days=days)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, db=Depends(get_db)):
    """删除单个任务（硬删除）"""
    svc = TaskService(db)
    try:
        await svc.delete_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")


@router.get("/{task_id}")
async def get_task(task_id: str, db=Depends(get_db)):
    svc = TaskService(db)
    try:
        task = await svc.get_by_id(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return _task_to_dict(task)


@router.post("/{task_id}/transition")
async def transition_task(task_id: str, body: TransitionRequest, db=Depends(get_db)):
    svc = TaskService(db)
    try:
        new_state = TaskState(body.new_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"未知状态: {body.new_state}")
    try:
        task = await svc.transition(task_id, new_state, agent=body.agent, reason=body.reason)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _task_to_dict(task)


@router.post("/{task_id}/dispatch")
async def dispatch_task(task_id: str, body: DispatchRequest, db=Depends(get_db)):
    svc = TaskService(db)
    try:
        await svc.request_dispatch(task_id, body.synapse, body.message)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {"status": "dispatched", "synapse": body.synapse}


@router.post("/{task_id}/progress")
async def add_progress(task_id: str, body: ProgressRequest, db=Depends(get_db)):
    svc = TaskService(db)
    try:
        task = await svc.add_progress(task_id, body.agent, body.content)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return _task_to_dict(task)


@router.patch("/{task_id}")
async def patch_task(task_id: str, body: PatchTaskRequest, db=Depends(get_db)):
    """部分更新任务字段（title / description / priority）"""
    svc = TaskService(db)
    try:
        task = await svc.patch_task(task_id, **body.model_dump(exclude_none=True))
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return _task_to_dict(task)


@router.put("/{task_id}/todos")
async def update_todos(task_id: str, body: TodosRequest, db=Depends(get_db)):
    svc = TaskService(db)
    try:
        task = await svc.update_todos(task_id, body.todos)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return _task_to_dict(task)
