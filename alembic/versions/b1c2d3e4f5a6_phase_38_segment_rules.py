"""Phase 38: Add segment_rules table for named RFM rules.

Revision ID: b1c2d3e4f5a6
Revises: a30b1c2d3e4f
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "b1c2d3e4f5a6"
down_revision = "a30b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "segment_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(20), nullable=False, server_default="#6366f1"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("r_min", sa.Integer, nullable=False, server_default="1"),
        sa.Column("r_max", sa.Integer, nullable=False, server_default="5"),
        sa.Column("f_min", sa.Integer, nullable=False, server_default="1"),
        sa.Column("f_max", sa.Integer, nullable=False, server_default="5"),
        sa.Column("m_min", sa.Integer, nullable=False, server_default="1"),
        sa.Column("m_max", sa.Integer, nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_segment_rules_tenant_priority",
        "segment_rules",
        ["tenant_id", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_segment_rules_tenant_priority", table_name="segment_rules")
    op.drop_table("segment_rules")

