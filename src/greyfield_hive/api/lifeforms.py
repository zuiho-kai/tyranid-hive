"""Read-only lifeform API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from greyfield_hive.db import get_db
from greyfield_hive.services.lifeform_service import LifeformService

router = APIRouter(prefix="/api/lifeforms", tags=["lifeforms"])


def _lifeform_to_dict(lifeform) -> dict:
    return {
        "id": lifeform.id,
        "key": lifeform.key,
        "kind": lifeform.kind.value if lifeform.kind else None,
        "name": lifeform.name,
        "display_name": lifeform.display_name,
        "persona_summary": lifeform.persona_summary,
        "lineage": lifeform.lineage,
        "status": lifeform.status.value if lifeform.status else None,
        "backing_synapse": lifeform.backing_synapse,
        "created_at": lifeform.created_at.isoformat() if lifeform.created_at else None,
        "updated_at": lifeform.updated_at.isoformat() if lifeform.updated_at else None,
    }


@router.get("")
async def list_lifeforms(db=Depends(get_db)):
    svc = LifeformService(db)
    return [_lifeform_to_dict(item) for item in await svc.list_all()]


@router.get("/{lifeform_id}")
async def get_lifeform(lifeform_id: str, db=Depends(get_db)):
    svc = LifeformService(db)
    item = await svc.get_by_id(lifeform_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"生命体不存在: {lifeform_id}")
    return _lifeform_to_dict(item)
