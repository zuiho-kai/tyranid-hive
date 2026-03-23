"""Submind 模型 —— 小主脑实体，三态管理（常驻/试验/休眠）"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, JSON, Enum as SAEnum, Index, Float

from greyfield_hive.db import Base


class SubmindState(str, enum.Enum):
    Active   = "active"    # 常驻：正常工作
    Trial    = "trial"     # 试验：赛马中
    Dormant  = "dormant"   # 休眠：暂停，保留生物质


class Submind(Base):
    """小主脑实体 —— 域内 CEO，有基因本源和生物质净值"""
    __tablename__ = "subminds"

    id          = Column(String(64), primary_key=True,
                         default=lambda: f"SM-{uuid.uuid4().hex[:8].upper()}")
    name        = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(128), default="")
    state       = Column(SAEnum(SubmindState), nullable=False,
                         default=SubmindState.Active)

    # 基因本源（谱系连续性决定身份）
    gene_seed   = Column(String(64), default="")   # 基因模板 ID
    lineage_id  = Column(String(36), nullable=False,
                         default=lambda: str(uuid.uuid4()))  # 谱系 UUID，重孵时更新

    # 域
    domains     = Column(JSON, default=list)        # ["coding", "devops"]

    # 生物质净值（从休眠点续算）
    biomass     = Column(Float, default=0.0)
    biomass_at_dormant = Column(Float, nullable=True)  # 休眠时快照

    # 前身继承（强制清空重孵时可继承 50% 战功）
    predecessor_id = Column(String(64), nullable=True)

    # 配置（YAML/JSON 格式的 gene 覆盖）
    config      = Column(JSON, default=dict)

    created_at  = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))
    dormant_at  = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_subminds_state", "state"),
        Index("ix_subminds_gene_seed", "gene_seed"),
    )

    def enter_dormant(self) -> None:
        """进入休眠，快照当前生物质"""
        self.state = SubmindState.Dormant
        self.biomass_at_dormant = self.biomass
        self.dormant_at = datetime.now(timezone.utc)

    def wake_up(self) -> None:
        """从休眠唤醒，从休眠点续算"""
        self.state = SubmindState.Active
        self.dormant_at = None

    def is_same_lineage(self, other: "Submind") -> bool:
        """判断是否同一谱系（同一个体）"""
        return self.lineage_id == other.lineage_id
