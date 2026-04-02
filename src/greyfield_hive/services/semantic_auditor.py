"""SemanticAuditor —— Playbook 语义聚类审计

Phase 3 关键词版（不用 embedding），定期检查：
  - 冗余：同簇内高度相似的 Playbook 对
  - 孤岛：过拟合单次任务的 Playbook
  - 模糊边界：域标签不清的 Playbook

审计报告供 EvolutionMaster 参考，决定合并/标记/退役。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.playbook import Playbook


@dataclass
class AuditReport:
    redundant_pairs:  list[tuple[str, str]] = field(default_factory=list)
    orphan_entries:   list[str]             = field(default_factory=list)
    fuzzy_boundaries: list[tuple[str, str]] = field(default_factory=list)
    total_playbooks:  int = 0

    @property
    def has_issues(self) -> bool:
        return bool(self.redundant_pairs or self.orphan_entries or self.fuzzy_boundaries)


def _tokenize(text: str) -> set[str]:
    """简易分词：按空白和标点拆分，过滤短词"""
    import re
    words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return {w for w in words if len(w) >= 2}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class SemanticAuditor:
    """Playbook 语义聚类审计器"""

    REDUNDANCY_THRESHOLD = 0.60    # Jaccard > 0.6 视为冗余
    ORPHAN_MIN_TOKENS    = 5       # 内容词数 < 5 视为孤岛

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def audit(self, domain: Optional[str] = None) -> AuditReport:
        """运行审计，返回报告"""
        q = select(Playbook).where(Playbook.is_active.is_(True))
        if domain:
            q = q.where(Playbook.domain == domain)
        result = await self._db.execute(q)
        playbooks = list(result.scalars().all())

        report = AuditReport(total_playbooks=len(playbooks))
        if len(playbooks) < 2:
            return report

        # 预分词
        pb_tokens: dict[str, set[str]] = {}
        for pb in playbooks:
            pb_tokens[pb.id] = _tokenize(pb.content or "")

        # 冗余检测：两两比较 Jaccard
        ids = list(pb_tokens.keys())
        slug_map = {pb.id: pb.slug for pb in playbooks}
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = _jaccard(pb_tokens[ids[i]], pb_tokens[ids[j]])
                if sim > self.REDUNDANCY_THRESHOLD:
                    report.redundant_pairs.append(
                        (slug_map[ids[i]], slug_map[ids[j]])
                    )

        # 孤岛检测：内容过少
        for pb in playbooks:
            tokens = pb_tokens.get(pb.id, set())
            if len(tokens) < self.ORPHAN_MIN_TOKENS:
                report.orphan_entries.append(pb.slug)

        # 模糊边界：不同域但内容相似度 > 0.4
        domain_map = {pb.id: pb.domain for pb in playbooks}
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if domain_map[ids[i]] != domain_map[ids[j]]:
                    sim = _jaccard(pb_tokens[ids[i]], pb_tokens[ids[j]])
                    if sim > 0.40:
                        report.fuzzy_boundaries.append(
                            (slug_map[ids[i]], slug_map[ids[j]])
                        )

        if report.has_issues:
            logger.info(
                f"[SemanticAuditor] 审计结果: "
                f"冗余={len(report.redundant_pairs)} "
                f"孤岛={len(report.orphan_entries)} "
                f"模糊边界={len(report.fuzzy_boundaries)}"
            )
        return report
