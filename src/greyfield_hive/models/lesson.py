"""Lessons 模型 —— 单次任务经验落盘（L3 层）

每次任务执行后，进化大师将失败/成功的关键信息写入 Lessons。
Tier 1-2 用简单衰减公式排序；Tier 3+ 升级为 BM25+embeddings 混合检索。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, Index

from greyfield_hive.db import Base


class Lesson(Base):
    """单次任务经验记录 —— 三层基因的 L3（最短时效，30 天自然衰减）"""
    __tablename__ = "lessons"

    id        = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 领域标签，用于 domain_match 评分
    domain    = Column(String(64), nullable=False, index=True)
    # 关键词标签（逗号分隔），用于 BM25 粗筛
    tags      = Column(String(256), default="")
    # 任务类型（success / failure / partial）
    outcome   = Column(String(16), nullable=False, default="unknown")
    # 经验正文（失败根因 / 成功策略）
    content   = Column(Text, nullable=False)
    # 关联的 Playbook 条目（可选）
    playbook_id = Column(String(36), nullable=True, index=True)
    # 使用频次（每次被检索命中后 +1）
    frequency = Column(Integer, default=0)
    # 最近使用时间
    last_used = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # 来源任务
    task_id   = Column(String(64), nullable=True)
    # 扩展（存储 embedding 向量路径或 JSON）
    meta      = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_lessons_domain_outcome", "domain", "outcome"),
        Index("ix_lessons_last_used", "last_used"),
    )
