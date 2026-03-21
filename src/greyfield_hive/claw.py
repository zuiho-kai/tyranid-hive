"""虫群核心 —— TyranidClaw

基于 OpenClaw 框架的主脑实现。
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass, field

from loguru import logger

from greyfield_hive.config import HiveConfig


@dataclass
class GovernanceMode:
    """治理模式定义（从文件加载）"""
    name: str
    display_name: str
    description: str
    levels: List[Dict[str, Any]]
    evolution: Dict[str, Any]
    trial_race: Dict[str, Any]


@dataclass
class SynapseDefinition:
    """小主脑定义（从文件加载）"""
    name: str
    display_name: str
    level: int
    state: str
    domains: List[str]
    model: Dict[str, Any]
    gene: str
    brood_limits: Dict[str, int]
    tools: Dict[str, List[str]]
    memory: Dict[str, Any]
    kill_mark_weights: Dict[str, float]


@dataclass
class GeneTemplate:
    """基因模板（从文件加载）"""
    name: str
    display_name: str
    level: int
    unit_type: str
    traits: List[str]
    system_prompt: str
    tool_preferences: Dict[str, List[str]]
    evolution: Dict[str, Any]
    execution: Dict[str, Any]
    memory: Dict[str, Any]


class ConfigLoader:
    """配置加载器 —— 从 YAML 文件加载治理模式、小主脑、基因"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.governance: Optional[GovernanceMode] = None
        self.synapses: Dict[str, SynapseDefinition] = {}
        self.genes: Dict[str, GeneTemplate] = {}

    def load_all(self) -> None:
        """加载所有配置"""
        self._load_governance()
        self._load_synapses()
        self._load_genes()
        logger.info(f"配置加载完成: 治理模式={self.governance.name if self.governance else None}, "
                   f"小主脑={len(self.synapses)}, 基因={len(self.genes)}")

    def _load_governance(self) -> None:
        """加载治理模式配置"""
        gov_dir = self.config_dir / "governance"
        if not gov_dir.exists():
            raise FileNotFoundError(f"治理模式目录不存在: {gov_dir}")

        # 默认加载 tyranid.yaml
        gov_file = gov_dir / "tyranid.yaml"
        if not gov_file.exists():
            raise FileNotFoundError(f"默认治理模式不存在: {gov_file}")

        with open(gov_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        gov_data = data.get("governance", {})
        self.governance = GovernanceMode(
            name=gov_data.get("name", "tyranid"),
            display_name=gov_data.get("display_name", "泰伦虫巢"),
            description=gov_data.get("description", ""),
            levels=gov_data.get("levels", []),
            evolution=gov_data.get("evolution", {}),
            trial_race=gov_data.get("trial_race", {}),
        )

    def _load_synapses(self) -> None:
        """加载小主脑配置"""
        syn_dir = self.config_dir / "synapses"
        if not syn_dir.exists():
            logger.warning(f"小主脑目录不存在: {syn_dir}")
            return

        for syn_file in syn_dir.glob("*.yaml"):
            try:
                with open(syn_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                syn_data = data.get("synapse", {})
                synapse = SynapseDefinition(
                    name=syn_data.get("name", syn_file.stem),
                    display_name=syn_data.get("display_name", syn_file.stem),
                    level=syn_data.get("level", 3),
                    state=syn_data.get("state", "resident"),
                    domains=syn_data.get("domains", []),
                    model=syn_data.get("model", {}),
                    gene=syn_data.get("gene", ""),
                    brood_limits=syn_data.get("brood_limits", {}),
                    tools=syn_data.get("tools", {}),
                    memory=syn_data.get("memory", {}),
                    kill_mark_weights=syn_data.get("kill_mark_weights", {}),
                )
                self.synapses[synapse.name] = synapse
                logger.debug(f"加载小主脑: {synapse.name}")
            except Exception as e:
                logger.error(f"加载小主脑失败 {syn_file}: {e}")

    def _load_genes(self) -> None:
        """加载基因模板"""
        genes_dir = self.config_dir / "genes"
        if not genes_dir.exists():
            logger.warning(f"基因目录不存在: {genes_dir}")
            return

        for gene_dir in genes_dir.iterdir():
            if not gene_dir.is_dir():
                continue

            gene_file = gene_dir / "gene.yaml"
            if not gene_file.exists():
                continue

            try:
                with open(gene_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                gene_data = data.get("gene", {})
                gene = GeneTemplate(
                    name=gene_data.get("name", gene_dir.name),
                    display_name=gene_data.get("display_name", gene_dir.name),
                    level=gene_data.get("level", 0),
                    unit_type=gene_data.get("unit_type", gene_dir.name),
                    traits=gene_data.get("traits", []),
                    system_prompt=gene_data.get("system_prompt", ""),
                    tool_preferences=gene_data.get("tool_preferences", {}),
                    evolution=gene_data.get("evolution", {}),
                    execution=gene_data.get("execution", {}),
                    memory=gene_data.get("memory", {}),
                )
                self.genes[gene.name] = gene
                logger.debug(f"加载基因: {gene.name}")
            except Exception as e:
                logger.error(f"加载基因失败 {gene_file}: {e}")


class TyranidClaw:
    """泰伦虫群主脑"""

    def __init__(self, config: HiveConfig, config_dir: str = "config"):
        self.config = config
        self.loader = ConfigLoader(config_dir)
        self.loader.load_all()

        # 验证配置
        self._validate_config()

        logger.info(f"TyranidClaw 初始化完成: {self.loader.governance.display_name}")

    def _validate_config(self) -> None:
        """验证配置一致性"""
        # 检查小主脑引用的基因是否存在
        for syn_name, synapse in self.loader.synapses.items():
            if synapse.gene and synapse.gene not in self.loader.genes:
                logger.warning(f"小主脑 {syn_name} 引用的基因 {synapse.gene} 不存在")

    async def submit_task(self, task: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """提交任务到虫群（主入口）"""
        # TODO: Phase E1 实现
        yield {"type": "status", "payload": {"state": "not_implemented"}}

    def get_governance_info(self) -> Dict[str, Any]:
        """获取治理模式信息"""
        gov = self.loader.governance
        return {
            "name": gov.name,
            "display_name": gov.display_name,
            "description": gov.description,
            "levels": len(gov.levels),
            "synapses": list(self.loader.synapses.keys()),
            "genes": list(self.loader.genes.keys()),
        }

    def get_synapse(self, name: str) -> Optional[SynapseDefinition]:
        """获取小主脑定义"""
        return self.loader.synapses.get(name)

    def get_gene(self, name: str) -> Optional[GeneTemplate]:
        """获取基因模板"""
        return self.loader.genes.get(name)

    def find_synapse_by_domain(self, domain: str) -> List[SynapseDefinition]:
        """根据领域查找小主脑"""
        return [
            syn for syn in self.loader.synapses.values()
            if domain in syn.domains
        ]
