"""Evolution Master REST API —— 自动经验萃取端点"""

from fastapi import APIRouter, Depends, Response

from greyfield_hive.db import get_db
from greyfield_hive.services.evolution_master import EvolutionMasterService

router = APIRouter(prefix="/api/evolution", tags=["evolution"])


@router.post("/domain/{domain}")
async def evolve_domain(domain: str, db=Depends(get_db)):
    """为指定域提炼经验，生成/更新 Playbook。

    - 成功经验数 >= 5 时触发
    - 返回 200 + 进化结果；经验不足时返回 204
    """
    svc = EvolutionMasterService(db)
    result = await svc.evolve_domain(domain)
    if result is None:
        return Response(status_code=204)
    return {
        "domain":           result.domain,
        "lessons_used":     result.lessons_used,
        "playbook_id":      result.playbook_id,
        "playbook_slug":    result.playbook_slug,
        "playbook_version": result.playbook_version,
        "is_new":           result.is_new,
    }


@router.post("/scan")
async def scan_and_evolve(db=Depends(get_db)):
    """全域扫描：对所有达到阈值的域触发进化。"""
    svc = EvolutionMasterService(db)
    results = await svc.scan_and_evolve()
    return {
        "evolved": [
            {
                "domain":           r.domain,
                "lessons_used":     r.lessons_used,
                "playbook_slug":    r.playbook_slug,
                "playbook_version": r.playbook_version,
                "is_new":           r.is_new,
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/status")
async def evolution_status(db=Depends(get_db)):
    """返回各域的经验统计，用于仪表盘展示进化状态。"""
    svc = EvolutionMasterService(db)
    domains = await svc.get_domain_status()
    return {
        "threshold": EvolutionMasterService.LESSON_THRESHOLD,
        "domains":   domains,
    }
