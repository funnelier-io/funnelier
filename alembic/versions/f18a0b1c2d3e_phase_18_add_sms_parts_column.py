"""Phase 18: Add sms_parts column, create sync_logs table

Revision ID: f18a0b1c2d3e
Revises: 2ed2da912eae
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "f18a0b1c2d3e"
down_revision = "2ed2da912eae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SMS parts column
    op.add_column("sms_logs", sa.Column("sms_parts", sa.Integer(), nullable=False, server_default="1"))

    # Sync logs table for ERP/CRM sync history
    op.create_table(
        "sync_logs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("sync_type", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(20), server_default="pull", nullable=True),
        sa.Column("status", sa.String(30), server_default="running", nullable=True),
        sa.Column("records_fetched", sa.Integer(), server_default="0", nullable=True),
        sa.Column("records_created", sa.Integer(), server_default="0", nullable=True),
        sa.Column("records_updated", sa.Integer(), server_default="0", nullable=True),
        sa.Column("records_skipped", sa.Integer(), server_default="0", nullable=True),
        sa.Column("records_failed", sa.Integer(), server_default="0", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("errors", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("details", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("triggered_by", sa.String(50), server_default="manual", nullable=True),
        sa.Column("triggered_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_source_connections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_logs_tenant_id", "sync_logs", ["tenant_id"])
    op.create_index("ix_sync_logs_data_source_id", "sync_logs", ["data_source_id"])
    op.create_index("ix_sync_logs_status", "sync_logs", ["status"])
    op.create_index("ix_sync_logs_tenant_status", "sync_logs", ["tenant_id", "status"])
    op.create_index("ix_sync_logs_tenant_started", "sync_logs", ["tenant_id", "started_at"])
    op.create_index("ix_sync_logs_source_started", "sync_logs", ["data_source_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_sync_logs_source_started", table_name="sync_logs")
    op.drop_index("ix_sync_logs_tenant_started", table_name="sync_logs")
    op.drop_index("ix_sync_logs_tenant_status", table_name="sync_logs")
    op.drop_index("ix_sync_logs_status", table_name="sync_logs")
    op.drop_index("ix_sync_logs_data_source_id", table_name="sync_logs")
    op.drop_index("ix_sync_logs_tenant_id", table_name="sync_logs")
    op.drop_table("sync_logs")
    op.drop_column("sms_logs", "sms_parts")

