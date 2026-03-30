"""虫巢任务模型 —— 状态机 + SQLAlchemy ORM"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, JSON, Enum as SAEnum, Index, ForeignKey

from greyfield_hive.db import Base


class TaskState(str, enum.Enum):
    """任务状态机 —— 泰伦虫群的孵化→执行→完成生命周期"""
    Incubating   = "Incubating"    # 孵化中：新任务，等待主脑路由
    Planning     = "Planning"      # 规划中：主脑拆解任务
    Reviewing    = "Reviewing"     # 复核中：主脑评审计划
    Spawning     = "Spawning"      # 生产中：已派发给小主脑/工作组
    Executing    = "Executing"     # 执行中：Unit 正在运行
    Consolidating = "Consolidating"  # 巩固中：进化大师复盘
    WaitingInput = "WaitingInput"    # 等待用户补充关键信息
    Complete     = "Complete"      # 完成（终态）
    Dormant      = "Dormant"       # 休眠：阻塞/等待
    Cancelled    = "Cancelled"     # 取消（终态）


TERMINAL_STATES = {TaskState.Complete, TaskState.Cancelled}

STATE_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.Incubating:    {TaskState.Planning, TaskState.Spawning, TaskState.WaitingInput, TaskState.Dormant, TaskState.Cancelled},
    TaskState.Planning:      {TaskState.Reviewing, TaskState.Spawning, TaskState.WaitingInput, TaskState.Dormant, TaskState.Cancelled},
    TaskState.Reviewing:     {TaskState.Spawning, TaskState.Planning, TaskState.WaitingInput, TaskState.Cancelled},
    TaskState.Spawning:      {TaskState.Executing, TaskState.WaitingInput, TaskState.Dormant, TaskState.Cancelled},
    TaskState.Executing:     {TaskState.Consolidating, TaskState.Complete, TaskState.WaitingInput, TaskState.Dormant, TaskState.Cancelled},
    TaskState.Consolidating: {TaskState.Complete, TaskState.Executing, TaskState.Cancelled},
    TaskState.WaitingInput:  {TaskState.Incubating, TaskState.Planning, TaskState.Reviewing, TaskState.Spawning, TaskState.Executing, TaskState.Cancelled},
    TaskState.Dormant:       {TaskState.Incubating, TaskState.Planning, TaskState.Reviewing, TaskState.Spawning, TaskState.Executing, TaskState.WaitingInput},
}

# 任务状态 → 默认派发目标（小主脑 ID）
STATE_SYNAPSE_MAP: dict[TaskState, str] = {
    TaskState.Incubating:    "overmind",
    TaskState.Planning:      "overmind",
    TaskState.Reviewing:     "overmind",
    TaskState.Consolidating: "evolution-master",
}

# 执行模式（由主脑在 Planning 阶段决策）
class ExecutionMode(str, enum.Enum):
    Solo   = "solo"    # 单主脑直接执行
    Trial  = "trial"   # 双路赛马，取优
    Chain  = "chain"   # 串行链
    Swarm  = "swarm"   # 并发 Unit 池


class Task(Base):
    """虫巢任务 —— 虫族以"战团"为任务单元孵化、执行、巩固"""
    __tablename__ = "tasks"

    # 主键：人类可读 ID
    id = Column(String(64), primary_key=True, default=lambda: f"BT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}")
    # UUID：API 使用
    task_uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    # 追踪链路：跨整个生命周期
    trace_id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))

    title       = Column(Text, nullable=False)
    description = Column(Text, default="")
    state       = Column(SAEnum(TaskState), nullable=False, default=TaskState.Incubating)
    priority    = Column(String(16), default="normal")  # low/normal/high/critical
    exec_mode   = Column(SAEnum(ExecutionMode), nullable=True)  # 由 Planning 阶段填入

    # 派发目标（小主脑 ID 或领域标签）
    assignee_synapse = Column(String(64), nullable=True)
    current_owner_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True)
    entry_lifeform_id = Column(String(64), ForeignKey("lifeforms.id", ondelete="SET NULL"), nullable=True)
    last_handoff_id = Column(String(64), nullable=True)
    creator          = Column(String(64), default="user")

    # 审计链：每次状态转换都追加一条记录
    flow_log     = Column(JSON, default=list)
    # 执行日志：小主脑/Unit 写入的进度记录
    progress_log = Column(JSON, default=list)
    # 子任务列表（Planning 阶段由主脑生成）
    todos        = Column(JSON, default=list)
    # 标签列表（自由文本，存储为 JSON 数组，如 ["bug","urgent"]）
    labels       = Column(JSON, default=list)
    # 父任务 ID（子任务分解时由主脑设置）
    parent_id    = Column(String(64), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    # 依赖任务列表（JSON 数组，存 task_id；所有依赖完成前不自动派发）
    depends_on   = Column(JSON, default=list)
    # 扩展元数据
    meta         = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_tasks_state", "state"),
        Index("ix_tasks_updated_at", "updated_at"),
        Index("ix_tasks_parent_id", "parent_id"),
        Index("ix_tasks_current_owner_lifeform_id", "current_owner_lifeform_id"),
    )

    def append_flow(self, from_state: Optional[str], to_state: str, agent: str, reason: str = "") -> None:
        """追加状态转换记录"""
        if self.flow_log is None:
            self.flow_log = []
        entry = {
            "from": from_state,
            "to":   to_state,
            "agent": agent,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.flow_log = list(self.flow_log) + [entry]

    def append_progress(self, agent: str, content: str) -> None:
        """追加执行进度"""
        if self.progress_log is None:
            self.progress_log = []
        entry = {"agent": agent, "content": content, "ts": datetime.now(timezone.utc).isoformat()}
        self.progress_log = list(self.progress_log) + [entry]
