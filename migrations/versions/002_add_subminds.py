"""新增 subminds 表

Revision ID: 002
Revises: 001
Create Date: 2026-03-23 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subminds",
        sa.Column("id",                 sa.String(64),  nullable=False),
        sa.Column("name",               sa.String(64),  nullable=False),
        sa.Column("display_name",       sa.String(128), nullable=True),
        sa.Column("state",              sa.String(16),  nullable=False),
        sa.Column("gene_seed",          sa.String(64),  nullable=True),
        sa.Column("lineage_id",         sa.String(36),  nullable=False),
        sa.Column("domains",            sa.JSON(),      nullable=True),
        sa.Column("biomass",            sa.Float(),     nullable=True),
        sa.Column("biomass_at_dormant", sa.Float(),     nullable=True),
        sa.Column("predecessor_id",     sa.String(64),  nullable=True),
        sa.Column("config",             sa.JSON(),      nullable=True),
        sa.Column("created_at",         sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",         sa.DateTime(timezone=True), nullable=True),
        sa.Column("dormant_at",         sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_subminds_state",     "subminds", ["state"])
    op.create_index("ix_subminds_gene_seed", "subminds", ["gene_seed"])


def downgrade() -> None:
    op.drop_index("ix_subminds_gene_seed", table_name="subminds")
    op.drop_index("ix_subminds_state",     table_name="subminds")
    op.drop_table("subminds")
