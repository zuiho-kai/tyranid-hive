"""KillMark 模型 —— 记录每次执行的战功（适存驱动机制）"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, Index

from greyfield_hive.db import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class KillMark(Base):
    """战功记录 —— 每次 Agent 执行后写入

    biomass_delta = weight × score
    适存度 = sum(biomass_delta × exp(−decay × days_since))
    """

    __tablename__ = "kill_marks"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    synapse_id = Column(String(64), nullable=False, index=True)   # e.g. "code-expert"
    task_id    = Column(String(36), nullable=True,  index=True)
    domain     = Column(String(64), nullable=False, default="general")
    mark_type  = Column(String(64), nullable=False)               # e.g. "code_quality"
    weight     = Column(Float,      nullable=False, default=1.0)  # 来自 kill_mark_weights
    score      = Column(Float,      nullable=False, default=1.0)  # 0.0~1.0
    biomass_delta = Column(Float,   nullable=False, default=0.0)  # weight × score
    created_at = Column(DateTime,   default=_utcnow, nullable=False)
    # Phase 1: Episode 关联（step 粒度记账）
    episode_id      = Column(String(36), nullable=True)
    episode_step_id = Column(String(36), nullable=True)
    drain_category  = Column(String(32), nullable=True)  # standby / execution / coordination

    __table_args__ = (
        Index("ix_kill_marks_synapse_created", "synapse_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<KillMark synapse={self.synapse_id} type={self.mark_type} "
            f"Δ={self.biomass_delta:.2f}>"
        )
