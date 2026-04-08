"""Phase 30: Add performance indexes for common query patterns.

Adds composite indexes to accelerate:
- Salesperson filtering on contacts
- Default sort by created_at on contacts
- Campaign analytics on sms_logs
- Trigram search on contact names (pg_trgm)

Revision ID: a30b1c2d3e4f
Revises: 0e2bd9f452fe
Create Date: 2026-04-08
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "a30b1c2d3e4f"
down_revision = "0e2bd9f452fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram search (safe if already exists)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # contacts — salesperson assignment queries
    op.create_index(
        "ix_contacts_tenant_assigned_to",
        "contacts",
        ["tenant_id", "assigned_to"],
    )

    # contacts — default sort order (newest first)
    op.create_index(
        "ix_contacts_tenant_created_at",
        "contacts",
        ["tenant_id", "created_at"],
    )

    # contacts — trigram index for ILIKE %…% name search
    op.execute(
        "CREATE INDEX ix_contacts_name_trgm ON contacts "
        "USING gin (name gin_trgm_ops)"
    )

    # sms_logs — campaign analytics joins
    op.create_index(
        "ix_sms_logs_tenant_campaign",
        "sms_logs",
        ["tenant_id", "campaign_id"],
    )

    # campaign_recipients — contact-level campaign history
    op.create_index(
        "ix_campaign_recipients_contact",
        "campaign_recipients",
        ["contact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_recipients_contact", table_name="campaign_recipients")
    op.drop_index("ix_sms_logs_tenant_campaign", table_name="sms_logs")
    op.execute("DROP INDEX IF EXISTS ix_contacts_name_trgm")
    op.drop_index("ix_contacts_tenant_created_at", table_name="contacts")
    op.drop_index("ix_contacts_tenant_assigned_to", table_name="contacts")

