"""Phase 34: Add approval_process_id to tenant_users for Camunda integration.

Adds a nullable approval_process_id column to the tenant_users table.
This stores the Camunda process instance ID when user registration
is orchestrated via the user_approval BPMN workflow.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_users",
        sa.Column("approval_process_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_users", "approval_process_id")

