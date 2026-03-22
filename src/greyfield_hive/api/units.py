"""小主脑 / Unit 元数据 API"""

from fastapi import APIRouter, HTTPException

from greyfield_hive.workers.dispatcher import SYNAPSE_META
from greyfield_hive.models.task import STATE_SYNAPSE_MAP
from greyfield_hive.config_loader import load_synapse_config, load_gene

router = APIRouter(prefix="/api/synapses", tags=["synapses"])


@router.get("")
async def list_synapses():
    """列出所有已知的小主脑（含 YAML 配置摘要）"""
    result = []
    for sid, meta in SYNAPSE_META.items():
        entry: dict = {"id": sid, **meta}
        cfg = load_synapse_config(sid)
        if cfg:
            entry["tier"] = cfg.get("tier", meta.get("tier", 3))
            entry["state"] = cfg.get("state", "resident")
            entry["domains"] = cfg.get("domains", [])
        result.append(entry)
    return result


@router.get("/routing/state-map")
async def get_state_synapse_map():
    """返回状态 → 小主脑路由表"""
    return {
        state.value: synapse
        for state, synapse in STATE_SYNAPSE_MAP.items()
    }


@router.get("/{synapse_id}")
async def get_synapse(synapse_id: str):
    """获取单个小主脑完整配置（元数据 + YAML 配置 + L2 基因）"""
    meta = SYNAPSE_META.get(synapse_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"小主脑不存在: {synapse_id}")

    entry: dict = {"id": synapse_id, **meta}

    cfg = load_synapse_config(synapse_id)
    if cfg:
        entry["config"] = cfg
        gene_id = cfg.get("gene")
        if gene_id:
            gene = load_gene(gene_id)
            if gene:
                entry["gene"] = gene

    return entry
