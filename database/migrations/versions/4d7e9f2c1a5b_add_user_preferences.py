"""add user preferences JSON column

Revision ID: 4d7e9f2c1a5b
Revises: 5f9c2d8e41a3
Create Date: 2026-09-04 12:00:00.000000

Adds:
- users.preferences (JSON, default {}): server-authoritative account
  preferences (e.g. {"theme": "dark"}). Written only through the
  authenticated preferences endpoints; never client-controlled identity
  or roles.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d7e9f2c1a5b'
down_revision: Union[str, Sequence[str], None] = '5f9c2d8e41a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'preferences',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'preferences')