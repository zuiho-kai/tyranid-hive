"""Structured responsibility handoffs between lifeforms."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text

from greyfield_hive.db import Base


class Handoff(Base):
    __tablename__ = "handoffs"

    id = Column(String(64), primary_key=True, default=lambda: f"HO-{uuid.uuid4().hex[:10].upper()}")
    task_id = Column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    from_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True, index=True)
    to_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True, index=True)
    reason = Column(Text, default="")
    scope = Column(Text, default="")
    expected_output = Column(Text, default="")
    return_to_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_handoffs_task_created", "task_id", "created_at"),
    )
