"""Episode 模型 —— 记录每次任务执行的完整行为链

每条 Episode 对应一次任务执行，包含：
  - 任务指纹（结构化特征）
  - 选择的执行模式及理由
  - 所有执行步骤（EpisodeStep）
  - 最终结果统计

EpisodeStep 对应 Episode 中的每个原子执行步骤，记录：
  - 执行者（synapse / actor）
  - 引用的基因（Playbook / Lesson ID）
  - token 成本、wall time
  - 产出物摘要
  - 失败分类（env / understanding / strategy / quality）
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, Integer, JSON, Text, Index, ForeignKey

from greyfield_hive.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Episode(Base):
    """一次任务执行的行为链入口"""

    __tablename__ = "episodes"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id    = Column(String(64), nullable=False, index=True)  # auto-creates ix_episodes_task_id
    # TaskFingerprint 序列化 JSON
    fingerprint        = Column(JSON, default=dict)
    chosen_mode        = Column(String(16), nullable=True)   # solo / trial / chain / swarm
    mode_justification = Column(Text, default="")
    total_token_cost   = Column(Integer, default=0)
    total_wall_time    = Column(Float,   default=0.0)        # 秒
    outcome            = Column(String(16), nullable=True, index=True)   # success / failure / partial
    human_corrections  = Column(Integer, default=0)
    created_at         = Column(DateTime(timezone=True), default=_utcnow, index=True)
    finished_at        = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Episode task={self.task_id} mode={self.chosen_mode} outcome={self.outcome}>"


class EpisodeStep(Base):
    """Episode 内的单个执行步骤"""

    __tablename__ = "episode_steps"

    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id   = Column(String(36), ForeignKey("episodes.id"), nullable=False, index=True)  # auto ix_episode_steps_episode_id
    step_index   = Column(Integer, default=0)
    actor        = Column(String(64), default="", index=True)   # synapse ID 或 "overmind"
    action_type  = Column(String(32), default="")     # analyze / execute / review / handoff
    # 引用的 Playbook / Lesson ID 列表
    genes_used   = Column(JSON, default=list)
    token_cost   = Column(Integer, default=0)
    wall_time    = Column(Float,   default=0.0)
    outcome      = Column(String(16), default="success")   # success / failure / skipped
    # env / understanding / strategy / quality（仅 outcome=failure 时有值）
    error_class  = Column(String(32), nullable=True)
    # 产出物摘要（key-value，不存原始大文本）
    artifacts    = Column(JSON, default=dict)
    # 被后续步骤复用的次数（每次复用时 +1）
    reused_by_count = Column(Integer, default=0)
    created_at   = Column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<EpisodeStep [{self.step_index}] actor={self.actor} "
            f"type={self.action_type} outcome={self.outcome}>"
        )
