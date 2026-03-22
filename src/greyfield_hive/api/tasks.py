"""任务 REST API —— CRUD + 状态流转"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from greyfield_hive.agents.overmind_agent import OvermindAgent
from greyfield_hive.db import get_db
from greyfield_hive.models.task import Task, TaskState
from greyfield_hive.services.lessons_bank import LessonsBank
from greyfield_hive.services.playbook_service import PlaybookService
from greyfield_hive.services.task_service import TaskService, InvalidTransitionError, TaskNotFoundError
from greyfield_hive.services.trial_race import TrialRaceService
from greyfield_hive.services.chain_runner import ChainRunnerService
from greyfield_hive.services.swarm_runner import SwarmRunnerService, SwarmUnit
from greyfield_hive.services.fitness_service import FitnessService
from greyfield_hive.workers.dispatcher import _SYNAPSE_DOMAIN

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Schemas ──────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    title:       str
    description: str = ""
    priority:    str = "normal"
    creator:     str = "user"
    assignee_synapse: Optional[str] = None
    meta:        dict = {}
    labels:      list[str] = []


class TransitionRequest(BaseModel):
    new_state: str
    agent:     str = "user"
    reason:    str = ""


class DispatchRequest(BaseModel):
    synapse:  str
    message:  str = ""


class TrialRequest(BaseModel):
    synapses: list[str]       # 恰好两个 synapse name
    message:  str = ""
    domain:   str = ""


class ChainRequest(BaseModel):
    synapses: list[str]       # 至少两个 synapse name，按顺序执行
    message:  str = ""
    domain:   str = ""


class SwarmUnitRequest(BaseModel):
    synapse: str
    message: str
    domain:  str = ""


class SwarmRequest(BaseModel):
    units:          list[SwarmUnitRequest]   # 至少一个 unit
    max_concurrent: int = 5


class ProgressRequest(BaseModel):
    agent:   str
    content: str


class TodosRequest(BaseModel):
    todos: list[dict]


class AppendTodoRequest(BaseModel):
    title: str


class PatchTaskRequest(BaseModel):
    title:       Optional[str]       = None
    description: Optional[str]       = None
    priority:    Optional[str]       = None
    labels:      Optional[list[str]] = None


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
        "labels":           task.labels or [],
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
        labels=body.labels,
    )
    return _task_to_dict(task)


_VALID_SORT_BY = {"updated_at", "created_at", "priority", "state"}
_VALID_ORDER   = {"asc", "desc"}


@router.get("")
async def list_tasks(
    state:    Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    q:        Optional[str] = Query(None, description="关键词搜索（title / description / id）"),
    label:    Optional[str] = Query(None, description="按标签过滤（精确匹配，如 bug）"),
    sort_by:  str            = Query("updated_at", description="排序字段: updated_at/created_at/priority/state"),
    order:    str            = Query("desc", description="排序方向: asc/desc"),
    limit:    int            = Query(50, ge=1, le=200),
    offset:   int            = Query(0, ge=0),
    db=Depends(get_db),
):
    if sort_by not in _VALID_SORT_BY:
        raise HTTPException(status_code=400, detail=f"无效 sort_by: {sort_by}，允许: {sorted(_VALID_SORT_BY)}")
    if order not in _VALID_ORDER:
        raise HTTPException(status_code=400, detail=f"无效 order: {order}，允许: asc/desc")
    svc = TaskService(db)
    state_enum = TaskState(state) if state else None
    tasks = await svc.list_tasks(
        state=state_enum, priority=priority, assignee=assignee, q=q,
        label=label, sort_by=sort_by, order=order, limit=limit, offset=offset,
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


@router.post("/{task_id}/trial")
async def trial_task(task_id: str, body: TrialRequest, db=Depends(get_db)):
    """赛马：两个 synapse 并行竞争同一任务，胜者经验自动入库"""
    if len(body.synapses) != 2:
        raise HTTPException(status_code=400, detail="synapses 必须恰好包含两个元素")
    # 验证任务存在
    svc = TaskService(db)
    try:
        task = await svc.get_by_id(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    race = TrialRaceService(db=db)
    result = await race.run(
        task_id=task_id,
        synapse_a=body.synapses[0],
        synapse_b=body.synapses[1],
        message=body.message or task.description or task.title,
        domain=body.domain,
        trace_id=task.trace_id or "",
    )

    return {
        "task_id":  task_id,
        "winner":   result.winner,
        "tie":      result.tie,
        "results": {
            s: {
                "returncode": r.returncode,
                "success":    r.success,
                "stdout":     r.stdout[:500],
                "stderr":     r.stderr[:200],
                "elapsed_sec": r.elapsed_sec,
            }
            for s, r in result.results.items()
        },
    }


@router.post("/{task_id}/dispatch")
async def dispatch_task(task_id: str, body: DispatchRequest, db=Depends(get_db)):
    """
    派发任务。synapse 传 "auto" 时，自动从适存度排行榜中选取最优 synapse。
    若 "auto" 且无历史战功，降级为 "overmind"。
    """
    synapse = body.synapse
    if synapse == "auto":
        # 用 message 猜测 domain（未指定时用 general）
        domain = "general"
        fitness_svc = FitnessService(db)
        best = await fitness_svc.recommend_synapse(domain=domain)
        synapse = best.synapse_id if best else "overmind"

    svc = TaskService(db)
    try:
        await svc.request_dispatch(task_id, synapse, body.message)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {"status": "dispatched", "synapse": synapse}


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
    """部分更新任务字段（title / description / priority / labels）"""
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


@router.post("/{task_id}/todos", status_code=201)
async def append_todo(task_id: str, body: AppendTodoRequest, db=Depends(get_db)):
    """追加单条 Todo，不替换已有清单"""
    svc = TaskService(db)
    try:
        task = await svc.append_todo(task_id, body.title)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return _task_to_dict(task)


@router.patch("/{task_id}/todos/{index}")
async def toggle_todo(task_id: str, index: int, db=Depends(get_db)):
    """切换指定索引 Todo 的完成状态（0-based）"""
    svc = TaskService(db)
    try:
        task = await svc.toggle_todo(task_id, index)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    except IndexError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _task_to_dict(task)


@router.post("/{task_id}/analyze")
async def analyze_task(task_id: str, db=Depends(get_db)):
    """主脑分析任务 —— 调用 Overmind LLM 拆解 todos、识别风险、推荐状态

    - 若未配置 ANTHROPIC_API_KEY，返回 503（降级提示）
    - 成功后：将 todos 注入任务、添加分析进度、推荐状态流转
    """
    svc = TaskService(db)
    try:
        task = await svc.get_by_id(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    agent = OvermindAgent()
    if not agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="Overmind LLM 不可用：未设置 ANTHROPIC_API_KEY",
        )

    # 从基因库检索相关上下文
    bank = LessonsBank(db)
    lessons = await bank.search(task_domain="general", top_k=5)
    pb_svc = PlaybookService(db)
    playbooks = await pb_svc.search(domain="general", top_k=3)

    result = await agent.analyze(
        title=task.title,
        description=task.description or "",
        lessons=[
            {"domain": l.domain, "content": l.content, "outcome": l.outcome}
            for l in lessons
        ],
        playbooks=[
            {"title": p.title, "content": p.content, "success_rate": p.success_rate,
             "version": p.version}
            for p in playbooks
        ],
    )

    # 将分析结果写入任务
    todos = [{"title": t, "done": False} for t in result.todos]
    if todos:
        task = await svc.update_todos(task_id, todos)

    summary_content = (
        f"[Overmind] 分析完成\n"
        f"概要：{result.summary}\n"
        f"领域：{result.domain}\n"
        f"Todos：{len(result.todos)} 条\n"
        f"风险：{'; '.join(result.risks) or '无'}\n"
        f"建议状态：{result.recommended_state}"
    )
    task = await svc.add_progress(task_id, "overmind", summary_content)

    return {
        "task":     _task_to_dict(task),
        "analysis": {
            "summary":             result.summary,
            "domain":              result.domain,
            "todos":               result.todos,
            "risks":               result.risks,
            "recommended_state":   result.recommended_state,
        },
    }


@router.post("/{task_id}/chain")
async def chain_task(task_id: str, body: ChainRequest, db=Depends(get_db)):
    """Chain Mode —— 顺序多 Agent 协作，前一阶段输出传入下一阶段

    - 至少需要 2 个 synapse
    - 任一阶段失败则 fail-fast 中止
    - 返回各阶段结果 + 最终输出
    """
    if len(body.synapses) < 2:
        raise HTTPException(status_code=400, detail="synapses 至少需要两个元素")

    svc = TaskService(db)
    try:
        task = await svc.get_by_id(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    chain = ChainRunnerService(db=db)
    result = await chain.run(
        task_id=task_id,
        synapses=body.synapses,
        message=body.message or task.description or task.title,
        domain=body.domain,
        trace_id=task.trace_id or "",
    )

    return {
        "task_id":      task_id,
        "success":      result.success,
        "final_output": result.final_output,
        "results": [
            {
                "synapse":     r.synapse,
                "returncode":  r.returncode,
                "success":     r.success,
                "stdout":      r.stdout[:500],
                "stderr":      r.stderr[:200],
                "elapsed_sec": r.elapsed_sec,
            }
            for r in result.results
        ],
    }


@router.post("/{task_id}/swarm")
async def swarm_task(task_id: str, body: SwarmRequest, db=Depends(get_db)):
    """Swarm Mode —— 并发 Unit 池，批量独立任务并行执行

    - units 中每个 unit 有独立的 synapse + message
    - 所有 units 并发执行（受 max_concurrent 限制）
    - 返回每个 unit 的结果 + 成功率统计
    """
    if not body.units:
        raise HTTPException(status_code=400, detail="units 不能为空")
    if body.max_concurrent < 1 or body.max_concurrent > 20:
        raise HTTPException(status_code=400, detail="max_concurrent 范围 1-20")

    svc = TaskService(db)
    try:
        task = await svc.get_by_id(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    units = [
        SwarmUnit(synapse=u.synapse, message=u.message, domain=u.domain)
        for u in body.units
    ]

    swarm = SwarmRunnerService(db=db)
    result = await swarm.run(
        task_id=task_id,
        units=units,
        trace_id=task.trace_id or "",
        max_concurrent=body.max_concurrent,
    )

    return {
        "task_id":       task_id,
        "total":         result.total,
        "success_count": result.success_count,
        "fail_count":    result.fail_count,
        "success_rate":  round(result.success_rate, 4),
        "all_success":   result.all_success,
        "results": [
            {
                "synapse":     r.synapse,
                "message":     r.message,
                "returncode":  r.returncode,
                "success":     r.success,
                "stdout":      r.stdout[:500],
                "stderr":      r.stderr[:200],
                "elapsed_sec": r.elapsed_sec,
            }
            for r in result.results
        ],
    }
