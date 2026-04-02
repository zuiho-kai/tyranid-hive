"""Policy 模型 —— 可追踪、可进化的策略实体

策略生命周期：
  candidate → shadow → active → decaying → retired

来源：
  seed      — 从 CLAUDE.md HEURISTIC / README 触发条件提取的初始策略
  distilled — 进化大师从 Episode 统计中蒸馏
  manual    — 人工创建

类别：
  mode_selection  — 什么情况下选什么执行模式
  gene_injection  — 哪些经验值得强制注入
  gate            — 原门禁规则的结构化表达
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy import Enum as SAEnum, Index

from greyfield_hive.db import Base


class PolicyState(str, enum.Enum):
    Candidate = "candidate"   # 新蒸馏，未验证
    Shadow    = "shadow"      # 旁路评估中（不影响真实决策）
    Active    = "active"      # 通过验证，影响决策
    Decaying  = "decaying"    # 近期命中率下降
    Retired   = "retired"     # 不再使用，保留可追溯


class Policy(Base):
    __tablename__ = "policies"

    id     = Column(String(36), primary_key=True,
                    default=lambda: str(uuid.uuid4()))
    slug   = Column(String(128), unique=True, nullable=False)
    domain = Column(String(64),  default="general", index=True)
    # mode_selection / gene_injection / gate
    category = Column(String(32), default="mode_selection")
    state    = Column(SAEnum(PolicyState), default=PolicyState.Candidate, index=True)
    # 策略自然语言描述
    content  = Column(Text, default="")
    # 结构化规则（可选），如 {"prefer_mode": "trial", "min_advantage": 0.2}
    rule_logic = Column(JSON, default=dict)

    # 命中统计
    hit_count   = Column(Integer, default=0)
    hit_success = Column(Integer, default=0)
    hit_fail    = Column(Integer, default=0)

    # shadow 预测统计
    shadow_predictions = Column(Integer, default=0)
    shadow_correct     = Column(Integer, default=0)

    # 时间戳
    created_at   = Column(DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc))
    last_hit_at  = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    retired_at   = Column(DateTime(timezone=True), nullable=True)

    # seed / distilled / manual
    source = Column(String(32), default="seed")

    __table_args__ = (
        Index("ix_policies_domain_state", "domain", "state"),
    )

    @property
    def shadow_accuracy(self) -> float:
        if self.shadow_predictions == 0:
            return 0.0
        return self.shadow_correct / self.shadow_predictions

    @property
    def hit_success_rate(self) -> float:
        total = self.hit_count
        return self.hit_success / total if total else 0.0

    def __repr__(self) -> str:
        return f"<Policy {self.slug} [{self.state}]>"
