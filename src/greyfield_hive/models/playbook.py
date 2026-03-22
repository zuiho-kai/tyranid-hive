"""Playbook 模型 —— L2 战术手册，版本化管理

Playbook ≠ Tool：Playbook 是"怎么用 tool 的经验描述"，不是可执行代码。
由进化大师从 Lessons 中提炼，版本化迭代，注入 Submind 的上下文。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, JSON, Index

from greyfield_hive.db import Base


class Playbook(Base):
    """战术手册条目 —— L2 层，版本化、可检索、可晋升"""
    __tablename__ = "playbooks"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 人类可读 slug，同一 slug 多版本共存
    slug       = Column(String(128), nullable=False, index=True)
    version    = Column(Integer, nullable=False, default=1)
    # 是否为当前激活版本（同 slug 只有一条 is_active=True）
    is_active  = Column(Boolean, nullable=False, default=True)

    # 所属领域（与 Lesson.domain 对应）
    domain     = Column(String(64), nullable=False, index=True)
    # 关键词标签
    tags       = Column(String(256), default="")
    # 标题（简短描述）
    title      = Column(String(256), nullable=False)
    # 正文（tool 调用模式的经验描述，Markdown）
    content    = Column(Text, nullable=False)

    # 来源 Lesson IDs（由哪些 Lesson 提炼而来）
    source_lessons = Column(JSON, default=list)
    # 使用次数
    use_count  = Column(Integer, default=0)
    # 成功率（0.0-1.0，由 Evolution Master 更新）
    success_rate = Column(Float, default=0.0)
    # 是否已被晋升为专化生物形态
    crystallized = Column(Boolean, default=False)
    # 备注（Evolution Master 写的评注）
    notes      = Column(Text, default="")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_playbooks_slug_version", "slug", "version", unique=True),
        Index("ix_playbooks_domain_active", "domain", "is_active"),
    )
