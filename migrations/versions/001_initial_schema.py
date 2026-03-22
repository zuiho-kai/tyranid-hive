"""初始数据库结构 —— Tasks / Lessons / Playbooks / BusEvents

Revision ID: 001
Revises:
Create Date: 2026-03-22 00:00:00.000000

此迁移对应 create_all() 的完整 Schema，适用于从零开始的 PostgreSQL 部署。
已存在 SQLite 数据库升级到 PostgreSQL 时，需先导出数据，迁移后重新导入。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tasks ─────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id",               sa.String(64),   nullable=False),
        sa.Column("task_uuid",        sa.String(36),   nullable=False),
        sa.Column("trace_id",         sa.String(36),   nullable=False),
        sa.Column("title",            sa.String(256),  nullable=False),
        sa.Column("description",      sa.Text(),       nullable=True),
        sa.Column("state",            sa.String(32),   nullable=False),
        sa.Column("priority",         sa.String(16),   nullable=False),
        sa.Column("exec_mode",        sa.String(16),   nullable=True),
        sa.Column("assignee_synapse", sa.String(64),   nullable=True),
        sa.Column("creator",          sa.String(64),   nullable=False),
        sa.Column("flow_log",         sa.JSON(),       nullable=True),
        sa.Column("progress_log",     sa.JSON(),       nullable=True),
        sa.Column("todos",            sa.JSON(),       nullable=True),
        sa.Column("meta",             sa.JSON(),       nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",       sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_state",    "tasks", ["state"])
    op.create_index("ix_tasks_priority", "tasks", ["priority"])
    op.create_index("ix_tasks_creator",  "tasks", ["creator"])
    op.create_index("ix_tasks_assignee_synapse", "tasks", ["assignee_synapse"])

    # ── lessons ───────────────────────────────────────────
    op.create_table(
        "lessons",
        sa.Column("id",          sa.String(36),  nullable=False),
        sa.Column("domain",      sa.String(64),  nullable=False),
        sa.Column("tags",        sa.String(256), nullable=True),
        sa.Column("outcome",     sa.String(16),  nullable=False),
        sa.Column("content",     sa.Text(),      nullable=False),
        sa.Column("playbook_id", sa.String(36),  nullable=True),
        sa.Column("frequency",   sa.Integer(),   nullable=True),
        sa.Column("last_used",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_id",     sa.String(64),  nullable=True),
        sa.Column("meta",        sa.JSON(),      nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lessons_domain",      "lessons", ["domain"])
    op.create_index("ix_lessons_playbook_id", "lessons", ["playbook_id"])

    # ── playbooks ─────────────────────────────────────────
    op.create_table(
        "playbooks",
        sa.Column("id",              sa.String(36),  nullable=False),
        sa.Column("slug",            sa.String(128), nullable=False),
        sa.Column("version",         sa.Integer(),   nullable=False),
        sa.Column("is_active",       sa.Boolean(),   nullable=False),
        sa.Column("domain",          sa.String(64),  nullable=False),
        sa.Column("tags",            sa.String(256), nullable=True),
        sa.Column("title",           sa.String(256), nullable=False),
        sa.Column("content",         sa.Text(),      nullable=False),
        sa.Column("source_lessons",  sa.JSON(),      nullable=True),
        sa.Column("use_count",       sa.Integer(),   nullable=True),
        sa.Column("success_rate",    sa.Float(),     nullable=True),
        sa.Column("crystallized",    sa.Boolean(),   nullable=True),
        sa.Column("notes",           sa.Text(),      nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",      sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_playbooks_slug",   "playbooks", ["slug"])
    op.create_index("ix_playbooks_domain", "playbooks", ["domain"])

    # ── bus_events ────────────────────────────────────────
    op.create_table(
        "bus_events",
        sa.Column("event_id",   sa.String(36),   nullable=False),
        sa.Column("trace_id",   sa.String(36),   nullable=True),
        sa.Column("topic",      sa.String(128),  nullable=False),
        sa.Column("event_type", sa.String(64),   nullable=False),
        sa.Column("producer",   sa.String(64),   nullable=True),
        sa.Column("payload",    sa.JSON(),       nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_bus_events_trace_id",   "bus_events", ["trace_id"])
    op.create_index("ix_bus_events_topic",      "bus_events", ["topic"])
    op.create_index("ix_bus_events_event_type", "bus_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("bus_events")
    op.drop_table("playbooks")
    op.drop_table("lessons")
    op.drop_table("tasks")
