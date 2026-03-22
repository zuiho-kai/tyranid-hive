"""小主脑 / Unit 元数据 API"""

from fastapi import APIRouter

from greyfield_hive.workers.dispatcher import SYNAPSE_META
from greyfield_hive.models.task import STATE_SYNAPSE_MAP, TaskState

router = APIRouter(prefix="/api/synapses", tags=["synapses"])


@router.get("")
async def list_synapses():
    """列出所有已知的小主脑"""
    return [
        {"id": sid, **meta}
        for sid, meta in SYNAPSE_META.items()
    ]


@router.get("/{synapse_id}")
async def get_synapse(synapse_id: str):
    meta = SYNAPSE_META.get(synapse_id)
    if not meta:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"小主脑不存在: {synapse_id}")
    return {"id": synapse_id, **meta}


@router.get("/routing/state-map")
async def get_state_synapse_map():
    """返回状态 → 小主脑路由表"""
    return {
        state.value: synapse
        for state, synapse in STATE_SYNAPSE_MAP.items()
    }
