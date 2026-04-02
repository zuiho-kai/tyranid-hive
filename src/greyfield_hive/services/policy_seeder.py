"""PolicySeeder —— 启动时将 config/seeds/policy_seeds.yaml 灌入 PolicyRegistry

幂等：slug 已存在的策略跳过，不重复创建。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.policy import PolicyState
from greyfield_hive.services.policy_registry import PolicyRegistry


_SEEDS_FILE = Path(__file__).parent.parent.parent.parent / "config" / "seeds" / "policy_seeds.yaml"


async def seed_policies(db: AsyncSession) -> int:
    """从 YAML 文件灌入初始策略，返回新建条数。"""
    seeds_path = _SEEDS_FILE
    if not seeds_path.exists():
        logger.warning(f"[PolicySeeder] 种子文件不存在: {seeds_path}")
        return 0

    try:
        with open(seeds_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"[PolicySeeder] 读取种子文件失败: {e}")
        return 0

    policies = data.get("policies", [])
    registry = PolicyRegistry(db)
    created = 0

    for p in policies:
        slug = p.get("slug", "")
        if not slug:
            continue
        state_str = p.get("state", "candidate")
        try:
            state = PolicyState(state_str)
        except ValueError:
            state = PolicyState.Candidate

        policy = await registry.create(
            slug=slug,
            content=p.get("content", ""),
            domain=p.get("domain", "general"),
            category=p.get("category", "mode_selection"),
            rule_logic=p.get("rule_logic") or {},
            source="seed",
            state=state,
        )
        # 判断是否新建（新建时 hit_count=0 且 created_at 刚写入）
        if policy.hit_count == 0 and policy.source == "seed":
            created += 1

    if created:
        logger.info(f"[PolicySeeder] 灌入 {created} 条初始策略")
    return created
