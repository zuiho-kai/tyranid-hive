"""基因库导出/导入 API —— 一次性备份或迁移 lessons + playbooks

GET  /api/genes/export          导出所有 lessons + playbooks（JSON bundle）
POST /api/genes/import          批量导入 lessons + playbooks（幂等：slug 冲突时跳过 playbook）
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from greyfield_hive.db import get_db
from greyfield_hive.models.lesson import Lesson
from greyfield_hive.models.playbook import Playbook
from greyfield_hive.services.lessons_bank import LessonsBank
from greyfield_hive.services.playbook_service import PlaybookService

router = APIRouter(prefix="/api/genes", tags=["genes"])


# ── export ──────────────────────────────────────────────────────────────

@router.get("/export")
async def export_genes(db=Depends(get_db)):
    """
    导出所有经验教训 + 作战手册为 JSON bundle。
    可用于备份、迁移到新实例、或与他人共享基因库。
    """
    lessons_rows = (await db.execute(select(Lesson).order_by(Lesson.created_at))).scalars().all()
    playbooks_rows = (await db.execute(
        select(Playbook).where(Playbook.is_active == True).order_by(Playbook.created_at)  # noqa: E712
    )).scalars().all()

    lessons = [
        {
            "domain":    l.domain,
            "content":   l.content,
            "outcome":   l.outcome,
            "tags":      [t for t in (l.tags or "").split(",") if t],
            "frequency": l.frequency or 0,
            "task_id":   l.task_id,
        }
        for l in lessons_rows
    ]

    playbooks = [
        {
            "slug":    p.slug,
            "domain":  p.domain,
            "title":   p.title,
            "content": p.content,
        }
        for p in playbooks_rows
    ]

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "lessons_count":   len(lessons),
        "playbooks_count": len(playbooks),
        "lessons":   lessons,
        "playbooks": playbooks,
    }


# ── import ──────────────────────────────────────────────────────────────

class ImportLessonItem(BaseModel):
    domain:   str
    content:  str
    outcome:  str = "success"
    tags:     list[str] = []
    task_id:  Optional[str] = None
    frequency: int = 0


class ImportPlaybookItem(BaseModel):
    slug:    str
    domain:  str
    title:   str
    content: str


class ImportRequest(BaseModel):
    lessons:   list[ImportLessonItem]   = []
    playbooks: list[ImportPlaybookItem] = []


@router.post("/import")
async def import_genes(body: ImportRequest, db=Depends(get_db)):
    """
    批量导入经验教训 + 作战手册（幂等）。
    - lessons：全部追加（不去重）。
    - playbooks：slug 已存在时跳过，不存在时创建。
    返回 {lessons_added, playbooks_added, playbooks_skipped}。
    """
    bank = LessonsBank(db)
    pb_svc = PlaybookService(db)

    lessons_added = 0
    for item in body.lessons:
        await bank.add(
            domain=item.domain,
            content=item.content,
            outcome=item.outcome,
            task_id=item.task_id,
            tags=item.tags,
        )
        lessons_added += 1

    playbooks_added = 0
    playbooks_skipped = 0
    for item in body.playbooks:
        existing = await pb_svc._get_active(item.slug)
        if existing is not None:
            playbooks_skipped += 1
            continue
        await pb_svc.create(
            slug=item.slug,
            domain=item.domain,
            title=item.title,
            content=item.content,
        )
        playbooks_added += 1

    await db.commit()

    return {
        "lessons_added":     lessons_added,
        "playbooks_added":   playbooks_added,
        "playbooks_skipped": playbooks_skipped,
    }
