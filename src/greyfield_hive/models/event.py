"""虫巢事件模型 —— 全量审计链落盘"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, JSON, Index

from greyfield_hive.db import Base


class HiveEvent(Base):
    """虫巢事件持久化 —— 每个总线事件同步写入，提供完整可观测性"""
    __tablename__ = "hive_events"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id   = Column(String(36), nullable=False, index=True)
    task_id    = Column(String(64), nullable=True, index=True)

    topic      = Column(String(128), nullable=False)
    event_type = Column(String(128), nullable=False)
    producer   = Column(String(64), nullable=False)

    payload    = Column(JSON, default=dict)
    meta       = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_events_trace_topic", "trace_id", "topic"),
    )
