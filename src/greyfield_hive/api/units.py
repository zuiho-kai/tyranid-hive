"""Synapse metadata API."""

from fastapi import APIRouter, HTTPException

from greyfield_hive.workers.dispatcher import SYNAPSE_META
from greyfield_hive.models.task import STATE_SYNAPSE_MAP
from greyfield_hive.config_loader import load_synapse_config, load_gene

router = APIRouter(prefix="/api/synapses", tags=["synapses"])

_CLEAN_META: dict[str, dict] = {
    "overmind": {
        "name": "Overmind",
        "role": "Task analysis and routing decisions",
        "emoji": "O",
    },
    "evolution-master": {
        "name": "Evolution Master",
        "role": "Lessons extraction and gene evolution",
        "emoji": "E",
    },
    "code-expert": {
        "name": "Code Expert",
        "role": "Implementation and debugging",
        "emoji": "C",
    },
    "research-analyst": {
        "name": "Research Analyst",
        "role": "Information gathering and analysis",
        "emoji": "R",
    },
    "finance-scout": {
        "name": "Finance Scout",
        "role": "Market data collection and finance analysis",
        "emoji": "F",
    },
}


def _merge_synapse_meta(synapse_id: str, meta: dict) -> dict:
    clean = _CLEAN_META.get(synapse_id, {})
    return {**meta, **clean}


@router.get("")
async def list_synapses():
    """Return all known synapses with clean display metadata."""
    result = []
    for sid, meta in SYNAPSE_META.items():
        entry: dict = {"id": sid, **_merge_synapse_meta(sid, meta)}
        cfg = load_synapse_config(sid)
        if cfg:
            entry["tier"] = cfg.get("tier", meta.get("tier", 3))
            entry["state"] = cfg.get("state", "resident")
            entry["domains"] = cfg.get("domains", [])
        result.append(entry)
    return result


@router.get("/routing/state-map")
async def get_state_synapse_map():
    """Return the task-state to synapse routing table."""
    return {state.value: synapse for state, synapse in STATE_SYNAPSE_MAP.items()}


@router.get("/{synapse_id}")
async def get_synapse(synapse_id: str):
    """Return merged synapse metadata, config, and gene info."""
    meta = SYNAPSE_META.get(synapse_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown synapse: {synapse_id}")

    entry: dict = {"id": synapse_id, **_merge_synapse_meta(synapse_id, meta)}

    cfg = load_synapse_config(synapse_id)
    if cfg:
        entry["config"] = cfg
        gene_id = cfg.get("gene")
        if gene_id:
            gene = load_gene(gene_id)
            if gene:
                entry["gene"] = gene

    return entry
