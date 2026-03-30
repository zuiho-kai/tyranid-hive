"""Resident lifeforms for the anthropomorphic hive shell."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SAEnum, Index, String, Text

from greyfield_hive.db import Base


class LifeformKind(str, enum.Enum):
    Sovereign = "sovereign"
    Submind = "submind"


class LifeformState(str, enum.Enum):
    Active = "active"
    Dormant = "dormant"
    Sealed = "sealed"


class Lifeform(Base):
    __tablename__ = "lifeforms"

    id = Column(String(64), primary_key=True, default=lambda: f"LF-{uuid.uuid4().hex[:10].upper()}")
    key = Column(String(64), nullable=False, unique=True)
    kind = Column(SAEnum(LifeformKind), nullable=False)
    name = Column(String(128), nullable=False)
    display_name = Column(String(128), nullable=False)
    persona_summary = Column(Text, default="")
    lineage = Column(String(64), default="")
    status = Column(SAEnum(LifeformState), nullable=False, default=LifeformState.Active)
    backing_synapse = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_lifeforms_kind_status", "kind", "status"),
    )
