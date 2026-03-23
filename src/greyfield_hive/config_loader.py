"""配置文件加载器 —— 读取 config/ 目录下的 YAML 配置"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CONFIG_ROOT = Path(__file__).parent.parent.parent / "config"


def load_synapse_config(synapse_name: str) -> dict[str, Any] | None:
    """加载指定小主脑的 YAML 配置，找不到返回 None"""
    path = _CONFIG_ROOT / "synapses" / f"{synapse_name}.yaml"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("synapse", data) if isinstance(data, dict) else None


def load_gene(gene_id: str) -> dict[str, Any] | None:
    """加载 L2 基因 YAML，按 gene_id 查找"""
    # gene_id 形如 "L2_synapse_overmind"
    if gene_id.startswith("L2_"):
        stem = gene_id[3:]          # "synapse_overmind"
        path = _CONFIG_ROOT / "genes" / "L2" / f"{stem}.yaml"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("gene", data) if isinstance(data, dict) else None
    return None


def list_synapse_names() -> list[str]:
    """返回所有已有 YAML 配置的小主脑名称"""
    synapse_dir = _CONFIG_ROOT / "synapses"
    if not synapse_dir.exists():
        return []
    return [p.stem for p in synapse_dir.glob("*.yaml")]
