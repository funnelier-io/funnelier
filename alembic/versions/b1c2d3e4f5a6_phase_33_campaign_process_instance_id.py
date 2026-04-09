"""Phase 33: Add process_instance_id to campaigns for Camunda integration.

Adds a nullable process_instance_id column and a composite index on
(tenant_id, process_instance_id) to the campaigns table.  This column
stores the Camunda process instance ID when the campaign lifecycle is
orchestrated via BPMS.

Revision ID: b1c2d3e4f5a6
Revises: a30b1c2d3e4f
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a30b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("process_instance_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_campaigns_tenant_process_instance",
        "campaigns",
        ["tenant_id", "process_instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_campaigns_tenant_process_instance", table_name="campaigns")
    op.drop_column("campaigns", "process_instance_id")

