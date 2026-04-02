"""Skill 模型 —— 从高频稳定任务模式蒸馏出的专化器官

不是新人格 Agent，而是半程序化的 Skill Appliance：
  - 固定工具图谱
  - 固定输入输出 schema
  - 固定预注入 Playbook
  - 固定异常恢复策略

生命周期：
  incubating → active → degrading → retired

结晶条件（全部满足）：
  - 最近 N 次任务结构高度相似
  - 路径稳定（选同一模式、同一工具链）
  - 胜率 > 80%
  - 平均 token 明显低于通用流程
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON
from sqlalchemy import Enum as SAEnum, Index

from greyfield_hive.db import Base


class SkillState(str, enum.Enum):
    Incubating = "incubating"  # 刚结晶，待验证
    Active     = "active"      # 验证通过，执行路由优先匹配
    Degrading  = "degrading"   # 近期成功率下降
    Retired    = "retired"     # 回收，重新探索


class Skill(Base):
    __tablename__ = "skills"

    id          = Column(String(36), primary_key=True,
                         default=lambda: str(uuid.uuid4()))
    slug        = Column(String(128), unique=True, nullable=False)
    domain      = Column(String(64), default="general", index=True)
    state       = Column(SAEnum(SkillState), default=SkillState.Incubating, index=True)
    # 器官内容描述
    description = Column(Text, default="")
    # 固定模式
    preferred_mode    = Column(String(16), default="solo")
    preferred_synapse = Column(String(64), default="code-expert")
    # 固定预注入的 Playbook slug 列表
    playbook_slugs    = Column(JSON, default=list)
    # 匹配条件：TaskFingerprint 的结构化匹配
    match_criteria    = Column(JSON, default=dict)
    # 性能指标
    avg_token_cost    = Column(Integer, default=0)
    avg_wall_time     = Column(Float, default=0.0)
    success_rate      = Column(Float, default=0.0)
    total_uses        = Column(Integer, default=0)
    # 结晶来源
    source_episode_count = Column(Integer, default=0)
    source_domain        = Column(String(64), default="")
    # 时间戳
    created_at   = Column(DateTime(timezone=True),
                          default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    retired_at   = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_skills_domain_state", "domain", "state"),
    )

    def __repr__(self) -> str:
        return f"<Skill {self.slug} [{self.state}] rate={self.success_rate:.0%}>"
