"""Phase 8: Add username column to tenant_users

Revision ID: a1b2c3d4e5f6
Revises: b0a6f0d6de83
Create Date: 2026-02-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str = 'b0a6f0d6de83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add username column (nullable initially for existing rows)
    op.add_column('tenant_users', sa.Column('username', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_tenant_users_username'), 'tenant_users', ['username'], unique=True)

    # Backfill: set username = email for existing rows
    op.execute("UPDATE tenant_users SET username = email WHERE username IS NULL")


def downgrade() -> None:
    op.drop_index(op.f('ix_tenant_users_username'), table_name='tenant_users')
    op.drop_column('tenant_users', 'username')
