"""Playbook REST API —— L2 战术手册 CRUD + 版本管理"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from greyfield_hive.db import get_db
from greyfield_hive.services.playbook_service import PlaybookService, PlaybookNotFoundError

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


# ── Schemas ──────────────────────────────────────────────

class CreatePlaybookRequest(BaseModel):
    slug:            str
    domain:          str
    title:           str
    content:         str
    tags:            list[str] = []
    source_lessons:  list[str] = []
    notes:           str = ""


class NewVersionRequest(BaseModel):
    content:         str
    title:           Optional[str] = None
    tags:            Optional[list[str]] = None
    source_lessons:  list[str] = []
    notes:           str = ""


class SearchRequest(BaseModel):
    domain:  str
    tags:    list[str] = []
    top_k:   int = 5


class RecordUsageRequest(BaseModel):
    success: bool


class PatchPlaybookRequest(BaseModel):
    title:   Optional[str] = None
    content: Optional[str] = None
    domain:  Optional[str] = None


def _pb_dict(pb) -> dict:
    return {
        "id":              pb.id,
        "slug":            pb.slug,
        "version":         pb.version,
        "is_active":       pb.is_active,
        "domain":          pb.domain,
        "tags":            pb.tags,
        "title":           pb.title,
        "content":         pb.content,
        "source_lessons":  pb.source_lessons or [],
        "use_count":       pb.use_count,
        "success_rate":    round(pb.success_rate or 0.0, 4),
        "crystallized":    pb.crystallized,
        "notes":           pb.notes,
        "created_at":      pb.created_at.isoformat() if pb.created_at else None,
        "updated_at":      pb.updated_at.isoformat() if pb.updated_at else None,
    }


# ── 端点 ──────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_playbook(body: CreatePlaybookRequest, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.create(
            slug=body.slug, domain=body.domain, title=body.title,
            content=body.content, tags=body.tags,
            source_lessons=body.source_lessons, notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _pb_dict(pb)


@router.get("")
async def list_playbooks(
    domain: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    svc = PlaybookService(db)
    pbs = await svc.list_active(domain=domain, limit=limit)
    return [_pb_dict(pb) for pb in pbs]


@router.get("/{pb_id}")
async def get_playbook(pb_id: str, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.get_by_id(pb_id)
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {pb_id}")
    return _pb_dict(pb)


@router.get("/slug/{slug}")
async def get_active_by_slug(slug: str, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.get_active(slug)
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {slug}")
    return _pb_dict(pb)


@router.get("/slug/{slug}/versions")
async def list_versions(slug: str, db=Depends(get_db)):
    svc = PlaybookService(db)
    versions = await svc.list_versions(slug)
    if not versions:
        raise HTTPException(status_code=404, detail=f"slug 不存在: {slug}")
    return [_pb_dict(pb) for pb in versions]


@router.post("/slug/{slug}/versions", status_code=201)
async def new_version(slug: str, body: NewVersionRequest, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.create_new_version(
            slug=slug, content=body.content, title=body.title,
            tags=body.tags, source_lessons=body.source_lessons, notes=body.notes,
        )
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"slug 不存在: {slug}")
    return _pb_dict(pb)


@router.post("/slug/{slug}/rollback/{version}")
async def rollback(slug: str, version: int, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.rollback(slug, version)
    except PlaybookNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _pb_dict(pb)


@router.post("/auto-crystallize")
async def auto_crystallize(
    use_count: int = Query(10, ge=1, description="最低使用次数阈值"),
    success_rate: float = Query(0.8, ge=0.0, le=1.0, description="最低成功率阈值"),
    db=Depends(get_db),
):
    """扫描所有活跃 Playbook，命中阈值（use_count + success_rate）则自动结晶。"""
    svc = PlaybookService(db)
    crystallized = await svc.auto_crystallize_scan(
        use_count_threshold=use_count,
        success_rate_threshold=success_rate,
    )
    return {
        "crystallized": len(crystallized),
        "playbooks": [_pb_dict(pb) for pb in crystallized],
    }


@router.post("/search")
async def search_playbooks(body: SearchRequest, db=Depends(get_db)):
    svc = PlaybookService(db)
    pbs = await svc.search(domain=body.domain, task_tags=body.tags, top_k=body.top_k)
    return [_pb_dict(pb) for pb in pbs]


@router.post("/{pb_id}/usage")
async def record_usage(pb_id: str, body: RecordUsageRequest, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.record_usage(pb_id, body.success)
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {pb_id}")
    return _pb_dict(pb)


@router.post("/{pb_id}/crystallize")
async def crystallize(pb_id: str, db=Depends(get_db)):
    svc = PlaybookService(db)
    try:
        pb = await svc.mark_crystallized(pb_id)
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {pb_id}")
    return _pb_dict(pb)


@router.patch("/{pb_id}")
async def patch_playbook(pb_id: str, body: PatchPlaybookRequest, db=Depends(get_db)):
    """部分更新 Playbook 字段（title/content/domain）"""
    svc = PlaybookService(db)
    try:
        pb = await svc.update(pb_id, **body.model_dump(exclude_none=True))
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {pb_id}")
    return _pb_dict(pb)


@router.post("/{pb_id}/deactivate")
async def deactivate_playbook(pb_id: str, db=Depends(get_db)):
    """归档 Playbook（设置 is_active=False）"""
    svc = PlaybookService(db)
    try:
        pb = await svc.set_active(pb_id, active=False)
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {pb_id}")
    return _pb_dict(pb)


@router.post("/{pb_id}/activate")
async def activate_playbook(pb_id: str, db=Depends(get_db)):
    """重新激活已归档的 Playbook（设置 is_active=True）"""
    svc = PlaybookService(db)
    try:
        pb = await svc.set_active(pb_id, active=True)
    except PlaybookNotFoundError:
        raise HTTPException(status_code=404, detail=f"Playbook 不存在: {pb_id}")
    return _pb_dict(pb)
