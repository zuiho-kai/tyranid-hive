"""OrganCrystallizer —— 从高频稳定任务模式中自动结晶专化器官

结晶条件（全部满足）：
  1. 同域同模式 Episode ≥ 20 次
  2. 成功率 > 80%
  3. 平均 token 低于全域平均（说明路径已稳定优化）
  4. 不存在同名器官

结晶产出：
  Skill 实体（incubating 状态），包含固定 mode/synapse/playbook。
  由 EvolutionMaster 定期调用。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.episode import Episode
from greyfield_hive.services.episode_store import EpisodeStore
from greyfield_hive.services.skill_registry import SkillRegistry

# 结晶阈值
CRYSTAL_MIN_EPISODES   = 20
CRYSTAL_MIN_SUCCESS    = 0.80
CRYSTAL_TOKEN_DISCOUNT = 0.80  # 低于全域平均的 80% 才算"高效"


class OrganCrystallizer:
    """扫描 Episode 历史，识别高频稳定模式并结晶为 Skill"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._ep_store = EpisodeStore(db)
        self._skill_reg = SkillRegistry(db)

    async def scan_and_crystallize(self, days: int = 60) -> list[str]:
        """扫描所有域，对符合条件的模式结晶。返回新建 skill slugs。"""
        # 按 domain+mode 聚合 Episode
        all_episodes = await self._ep_store.query_by_domain("", days=days)
        # 自行按 fingerprint.domain 分组
        domain_mode_groups: dict[tuple[str, str], list[Episode]] = defaultdict(list)
        global_token_sum = 0
        global_count = 0

        for ep in all_episodes:
            if not ep.chosen_mode or not ep.outcome or not ep.finished_at:
                continue
            fp = ep.fingerprint or {}
            domain = fp.get("domain", "general")
            domain_mode_groups[(domain, ep.chosen_mode)].append(ep)
            if ep.total_token_cost:
                global_token_sum += ep.total_token_cost
                global_count += 1

        global_avg_token = global_token_sum / global_count if global_count > 0 else 999999

        new_slugs: list[str] = []
        for (domain, mode), episodes in domain_mode_groups.items():
            slug = await self._try_crystallize(
                domain, mode, episodes, global_avg_token
            )
            if slug:
                new_slugs.append(slug)

        if new_slugs:
            logger.info(f"[OrganCrystallizer] 本轮结晶 {len(new_slugs)} 个器官: {new_slugs}")
        return new_slugs

    async def _try_crystallize(
        self,
        domain: str,
        mode: str,
        episodes: list[Episode],
        global_avg_token: float,
    ) -> Optional[str]:
        """对一个 domain+mode 组合尝试结晶"""
        total = len(episodes)
        if total < CRYSTAL_MIN_EPISODES:
            return None

        success_count = sum(1 for e in episodes if e.outcome == "success")
        success_rate = success_count / total

        if success_rate < CRYSTAL_MIN_SUCCESS:
            return None

        # token 效率检查
        token_sum = sum(e.total_token_cost for e in episodes if e.total_token_cost)
        token_count = sum(1 for e in episodes if e.total_token_cost)
        avg_token = token_sum / token_count if token_count > 0 else 0
        if avg_token > global_avg_token * CRYSTAL_TOKEN_DISCOUNT:
            return None

        # 提取最常用的 synapse（从 fingerprint 的 structural_tags）
        tag_counts: dict[str, int] = defaultdict(int)
        for ep in episodes:
            for tag in (ep.fingerprint or {}).get("structural_tags", []):
                tag_counts[tag] += 1
        top_tags = sorted(tag_counts, key=lambda t: tag_counts[t], reverse=True)[:5]

        avg_wall = sum(e.total_wall_time for e in episodes) / total

        slug = f"organ-{domain}-{mode}"
        skill = await self._skill_reg.create(
            slug=slug,
            domain=domain,
            description=(
                f"从 {total} 次 {domain}/{mode} Episode 中结晶。"
                f"成功率 {success_rate:.0%}，平均 token {avg_token:.0f}，"
                f"平均耗时 {avg_wall:.1f}s"
            ),
            preferred_mode=mode,
            match_criteria={"structural_tags": top_tags, "domain": domain},
            avg_token_cost=int(avg_token),
            avg_wall_time=round(avg_wall, 2),
            success_rate=round(success_rate, 3),
            source_episode_count=total,
        )

        # 新建 → 达到阈值直接激活（因为结晶条件已经很严格）
        if skill.state.value == "incubating":
            await self._skill_reg.activate(skill.id)
            logger.info(
                f"[OrganCrystallizer] 结晶+激活: {slug} "
                f"rate={success_rate:.0%} episodes={total} tokens={avg_token:.0f}"
            )
            return slug

        return None
