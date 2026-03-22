"""基因加载器 —— 从 genes/L2/ 目录读取 Synapse L2 基因 YAML

提供：
  GeneLoader.get_system_prompt(synapse_id)  → str  角色系统提示词
  GeneLoader.get_gene(synapse_id)           → dict YAML gene 节点

内置 fallback：YAML 不存在时返回通用提示词，确保 Dispatcher 不因缺文件崩溃。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# genes/L2/ 目录（主路径）：
#   src/greyfield_hive/services/gene_loader.py → ../../../../genes/L2/
_GENES_DIR: Path = Path(__file__).parents[3] / "genes" / "L2"

# config/genes/L2/ 目录（次路径，含 context_injection / constraints）：
_CONFIG_GENES_DIR: Path = Path(__file__).parents[3] / "config" / "genes" / "L2"

# 通用 fallback 提示词（当 YAML 不存在时使用）
_FALLBACK_PROMPT = (
    "你是 Tyranid Hive 虫群的 Synapse（小主脑）。\n"
    "请认真阅读 [HIVE CONTEXT] 中的历史经验和作战手册，完成你的任务。\n"
    "输出结果必须可验证，包含核心结论和关键步骤。"
)


class GeneLoader:
    """L2 基因文件加载器（单例友好，可多次调用）"""

    def __init__(self, genes_dir: Path | str | None = None) -> None:
        self._dir = Path(genes_dir) if genes_dir else _GENES_DIR
        self._cache: dict[str, dict] = {}

    # ── 公共接口 ─────────────────────────────────────────

    def get_system_prompt(self, synapse_id: str) -> str:
        """返回指定 Synapse 的角色系统提示词。若 YAML 不存在则返回 fallback。"""
        gene = self.get_gene(synapse_id)
        if gene:
            return gene.get("system_prompt", _FALLBACK_PROMPT).strip()
        return _FALLBACK_PROMPT

    def get_gene(self, synapse_id: str) -> Optional[dict]:
        """加载并缓存 YAML gene 节点，失败时返回 None。"""
        if synapse_id in self._cache:
            return self._cache[synapse_id]

        path = self._find_yaml(synapse_id)
        if path is None:
            logger.debug(f"[GeneLoader] 未找到 L2 基因文件: {synapse_id}")
            self._cache[synapse_id] = {}
            return None

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            gene = raw.get("gene", {}) if isinstance(raw, dict) else {}
            self._cache[synapse_id] = gene
            logger.debug(f"[GeneLoader] 已加载 L2 基因: {synapse_id} ({path.name})")
            return gene or None
        except Exception as e:
            logger.warning(f"[GeneLoader] 解析失败 {path}: {e}")
            self._cache[synapse_id] = {}
            return None

    def list_synapses(self) -> list[str]:
        """列出 genes/L2/ 目录下所有可用的 Synapse ID。"""
        if not self._dir.exists():
            return []
        result = []
        for f in sorted(self._dir.glob("synapse_*.yaml")):
            raw = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "gene" in raw:
                sid = raw["gene"].get("synapse_id")
                if sid:
                    result.append(sid)
        return result

    def invalidate(self, synapse_id: str | None = None) -> None:
        """清除缓存（热重载时使用）。None 表示清除全部。"""
        if synapse_id is None:
            self._cache.clear()
        else:
            self._cache.pop(synapse_id, None)

    # ── 内部辅助 ─────────────────────────────────────────

    def _find_yaml(self, synapse_id: str) -> Optional[Path]:
        """按优先级探测 YAML 文件路径：
        1. 主路径（genes/L2/）精确匹配
        2. 主路径连字符→下划线匹配
        3. 主路径 synapse_id 字段扫描
        4. 备用路径（config/genes/L2/）同样逻辑
        """
        # 组装候选目录（主路径优先）
        candidate_dirs = [self._dir]
        if _CONFIG_GENES_DIR != self._dir and _CONFIG_GENES_DIR.exists():
            candidate_dirs.append(_CONFIG_GENES_DIR)

        normalized = synapse_id.replace("-", "_")

        for search_dir in candidate_dirs:
            if not search_dir.exists():
                continue
            # 精确匹配
            for stem in (f"synapse_{synapse_id}", f"synapse_{normalized}"):
                p = search_dir / f"{stem}.yaml"
                if p.exists():
                    return p
            # 扫描 gene.synapse_id 字段
            for f in search_dir.glob("synapse_*.yaml"):
                try:
                    raw = yaml.safe_load(f.read_text(encoding="utf-8"))
                    if not isinstance(raw, dict):
                        continue
                    gene = raw.get("gene", {})
                    if gene.get("synapse_id") == synapse_id or gene.get("id", "").endswith(normalized):
                        return f
                except Exception:
                    continue
        return None


# ── 模块级单例（可被 Dispatcher 直接 import 使用）─────────────────
_default_loader: GeneLoader | None = None


def get_gene_loader() -> GeneLoader:
    global _default_loader
    if _default_loader is None:
        _default_loader = GeneLoader()
    return _default_loader
