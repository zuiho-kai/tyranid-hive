"""适存度 API —— 战功记录 + 小主脑排行榜"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from greyfield_hive.db import get_db
from greyfield_hive.services.fitness_service import FitnessService

router = APIRouter(prefix="/api/fitness", tags=["fitness"])


class RecordRequest(BaseModel):
    synapse_id: str
    task_id:    str = ""
    domain:     str = "general"
    success:    bool = True
    score:      float = 1.0   # 0.0~1.0


@router.get("/leaderboard")
async def leaderboard(limit: int = 20, db=Depends(get_db)):
    """返回所有小主脑的适存度排行榜（含战功统计）"""
    svc = FitnessService(db)
    scores = await svc.get_leaderboard(limit=limit)
    return {
        "total": len(scores),
        "scores": [
            {
                "synapse_id":    s.synapse_id,
                "fitness":       s.fitness,
                "raw_biomass":   s.raw_biomass,
                "mark_count":    s.mark_count,
                "success_count": s.success_count,
                "fail_count":    s.fail_count,
                "success_rate":  round(s.success_rate, 4),
            }
            for s in scores
        ],
    }


@router.get("/{synapse_id}")
async def synapse_fitness(synapse_id: str, db=Depends(get_db)):
    """返回单个小主脑的适存度分数 + 最近战功"""
    svc = FitnessService(db)
    score = await svc.compute_fitness(synapse_id)
    history = await svc.get_synapse_history(synapse_id, limit=20)
    return {
        "synapse_id":    score.synapse_id,
        "fitness":       score.fitness,
        "raw_biomass":   score.raw_biomass,
        "mark_count":    score.mark_count,
        "success_count": score.success_count,
        "fail_count":    score.fail_count,
        "success_rate":  round(score.success_rate, 4),
        "recent_marks": [
            {
                "id":             m.id[:8],
                "mark_type":      m.mark_type,
                "domain":         m.domain,
                "biomass_delta":  m.biomass_delta,
                "score":          m.score,
                "created_at":     m.created_at.isoformat() if m.created_at else None,
            }
            for m in history
        ],
    }


@router.post("/record")
async def record_kill_mark(body: RecordRequest, db=Depends(get_db)):
    """手动记录战功（通常由内部服务调用，也可手动触发）"""
    if not 0.0 <= body.score <= 1.0:
        raise HTTPException(status_code=400, detail="score 范围 0.0~1.0")
    svc = FitnessService(db)
    marks = await svc.record_execution(
        synapse_id=body.synapse_id,
        task_id=body.task_id or None,
        domain=body.domain,
        success=body.success,
        score=body.score,
    )
    await db.commit()
    return {
        "recorded": len(marks),
        "synapse_id": body.synapse_id,
        "marks": [
            {"mark_type": m.mark_type, "biomass_delta": m.biomass_delta}
            for m in marks
        ],
    }
