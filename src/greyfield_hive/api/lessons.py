"""Lessons REST API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from greyfield_hive.db import get_db
from greyfield_hive.services.lessons_bank import LessonsBank

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class AddLessonRequest(BaseModel):
    domain:      str
    content:     str
    outcome:     str = "unknown"
    tags:        list[str] = []
    task_id:     Optional[str] = None
    playbook_id: Optional[str] = None
    meta:        dict = {}


class SearchRequest(BaseModel):
    domain:    str
    tags:      list[str] = []
    query:     str = ""
    top_k:     int = 5


def _lesson_dict(l) -> dict:
    return {
        "id":          l.id,
        "domain":      l.domain,
        "tags":        l.tags,
        "outcome":     l.outcome,
        "content":     l.content,
        "playbook_id": l.playbook_id,
        "frequency":   l.frequency,
        "last_used":   l.last_used.isoformat() if l.last_used else None,
        "task_id":     l.task_id,
        "created_at":  l.created_at.isoformat() if l.created_at else None,
    }


@router.post("", status_code=201)
async def add_lesson(body: AddLessonRequest, db=Depends(get_db)):
    bank = LessonsBank(db)
    lesson = await bank.add(
        domain=body.domain,
        content=body.content,
        outcome=body.outcome,
        tags=body.tags,
        task_id=body.task_id,
        playbook_id=body.playbook_id,
        meta=body.meta,
    )
    return _lesson_dict(lesson)


@router.post("/search")
async def search_lessons(body: SearchRequest, db=Depends(get_db)):
    bank = LessonsBank(db)
    results = await bank.search(
        task_domain=body.domain,
        task_tags=body.tags,
        query=body.query,
        top_k=body.top_k,
    )
    return [_lesson_dict(l) for l in results]


@router.get("")
async def list_lessons(
    domain: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    bank = LessonsBank(db)
    if domain:
        lessons = await bank.list_by_domain(domain, limit=limit)
    else:
        from sqlalchemy import select
        from greyfield_hive.models.lesson import Lesson
        result = await db.execute(select(Lesson).order_by(Lesson.last_used.desc()).limit(limit))
        lessons = list(result.scalars().all())
    return [_lesson_dict(l) for l in lessons]


@router.get("/{lesson_id}")
async def get_lesson(lesson_id: str, db=Depends(get_db)):
    bank = LessonsBank(db)
    lesson = await bank.get(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson 不存在: {lesson_id}")
    return _lesson_dict(lesson)


@router.delete("/expired")
async def purge_expired(days: int = Query(30, ge=1), db=Depends(get_db)):
    bank = LessonsBank(db)
    count = await bank.delete_expired(days=days)
    return {"deleted": count, "threshold_days": days}
