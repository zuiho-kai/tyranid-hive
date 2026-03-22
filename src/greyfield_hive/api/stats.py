"""综合统计 API —— 任务 + 经验库 + 作战手册一览"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from greyfield_hive.db import get_db
from greyfield_hive.models.task import Task
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
