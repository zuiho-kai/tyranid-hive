"""Task ownership assignments between resident lifeforms."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text

from greyfield_hive.db import Base


class AssignmentStatus(str, enum.Enum):
    Active = "active"
    Completed = "completed"
    Aborted = "aborted"


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(String(64), primary_key=True, default=lambda: f"AS-{uuid.uuid4().hex[:10].upper()}")
    task_id = Column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_by_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text, default="")
    scope = Column(Text, default="")
    expected_output = Column(Text, default="")
    status = Column(SAEnum(AssignmentStatus), nullable=False, default=AssignmentStatus.Active)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_assignments_task_status", "task_id", "status"),
    )
