"""综合统计 API —— 任务 + 经验库 + 作战手册一览"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_

from greyfield_hive.db import get_db
from greyfield_hive.models.task import Task, TaskState
from greyfield_hive.models.lesson import Lesson
from greyfield_hive.models.playbook import Playbook

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def overview(db=Depends(get_db)):
    """返回系统全量统计：任务 + 经验库 + 作战手册"""

    # ── 任务统计 ─────────────────────────────────────────
    task_rows = (await db.execute(
        select(Task.state, func.count(Task.id)).group_by(Task.state)
    )).all()
    by_state: dict[str, int] = {row[0]: row[1] for row in task_rows}
    total_tasks = sum(by_state.values())

    # ── 经验库统计 ────────────────────────────────────────
    lesson_total = (await db.execute(select(func.count(Lesson.id)))).scalar_one()

    lesson_by_domain_rows = (await db.execute(
        select(Lesson.domain, func.count(Lesson.id)).group_by(Lesson.domain)
    )).all()
    lesson_by_domain: dict[str, int] = {row[0]: row[1] for row in lesson_by_domain_rows}

    lesson_by_outcome_rows = (await db.execute(
        select(Lesson.outcome, func.count(Lesson.id)).group_by(Lesson.outcome)
    )).all()
    lesson_by_outcome: dict[str, int] = {row[0]: row[1] for row in lesson_by_outcome_rows}

    # 最活跃经验（frequency 最高的 5 条）
    top_lessons_rows = (await db.execute(
        select(Lesson.id, Lesson.domain, Lesson.content, Lesson.frequency)
        .order_by(Lesson.frequency.desc())
        .limit(5)
    )).all()
    top_lessons = [
        {"id": r[0], "domain": r[1], "content": r[2][:80], "frequency": r[3]}
        for r in top_lessons_rows
    ]

    # ── 作战手册统计 ──────────────────────────────────────
    pb_total = (await db.execute(select(func.count(Playbook.id)))).scalar_one()
    pb_active = (await db.execute(
        select(func.count(Playbook.id)).where(Playbook.is_active == True)
    )).scalar_one()
    pb_crystallized = (await db.execute(
        select(func.count(Playbook.id)).where(Playbook.crystallized == True)
    )).scalar_one()

    pb_by_domain_rows = (await db.execute(
        select(Playbook.domain, func.count(Playbook.id))
        .where(Playbook.is_active == True)
        .group_by(Playbook.domain)
    )).all()
    pb_by_domain: dict[str, int] = {row[0]: row[1] for row in pb_by_domain_rows}

    return {
        "tasks": {
            "total":    total_tasks,
            "by_state": by_state,
        },
        "lessons": {
            "total":      lesson_total,
            "by_domain":  lesson_by_domain,
            "by_outcome": lesson_by_outcome,
            "top_active": top_lessons,
        },
        "playbooks": {
            "total":       pb_total,
            "active":      pb_active,
            "crystallized": pb_crystallized,
            "by_domain":   pb_by_domain,
        },
    }


@router.get("/timeline")
async def timeline(
    days: int = Query(30, ge=1, le=90, description="统计最近 N 天（1-90）"),
    db=Depends(get_db),
):
    """生物质净值曲线 —— 按天聚合：任务创建/完成数 + 经验新增数 + 累计净值

    net_biomass = 累计已完成任务数（反映系统"成长"趋势）
    """
    now = datetime.now(timezone.utc)
    # 生成最近 N 天的日期列表（从最早到最新）
    date_list = [(now - timedelta(days=days - 1 - i)).date() for i in range(days)]

    # 查询指定时间窗口内的数据
    window_start = datetime.combine(date_list[0], datetime.min.time()).replace(tzinfo=timezone.utc)

    task_rows = (await db.execute(
        select(Task.created_at, Task.state)
        .where(Task.created_at >= window_start)
    )).all()

    lesson_rows = (await db.execute(
        select(Lesson.created_at)
        .where(Lesson.created_at >= window_start)
    )).all()

    # 查询所有已完成任务数（用于计算累计净值基准）
    prior_completed = (await db.execute(
        select(func.count(Task.id))
        .where(Task.state == TaskState.Complete, Task.created_at < window_start)
    )).scalar_one() or 0

    # 按日聚合
    tasks_created: dict[str, int] = {}
    tasks_completed: dict[str, int] = {}
    lessons_added: dict[str, int] = {}

    for row in task_rows:
        if row.created_at is None:
            continue
        d = row.created_at.date().isoformat()
        tasks_created[d] = tasks_created.get(d, 0) + 1
        if row.state == TaskState.Complete:
            tasks_completed[d] = tasks_completed.get(d, 0) + 1

    for row in lesson_rows:
        if row.created_at is None:
            continue
        d = row.created_at.date().isoformat()
        lessons_added[d] = lessons_added.get(d, 0) + 1

    # 构建 time-series points，计算累计净值
    points = []
    cumulative = prior_completed
    for date in date_list:
        ds = date.isoformat()
        completed_today = tasks_completed.get(ds, 0)
        cumulative += completed_today
        points.append({
            "date":            ds,
            "tasks_created":   tasks_created.get(ds, 0),
            "tasks_completed": completed_today,
            "lessons_added":   lessons_added.get(ds, 0),
            "net_biomass":     cumulative,
        })

    return {"days": days, "points": points}
