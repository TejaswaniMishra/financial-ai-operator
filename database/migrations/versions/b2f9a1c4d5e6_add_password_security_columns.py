"""add password security columns to users

Revision ID: b2f9a1c4d5e6
Revises: a663d2440b27
Create Date: 2026-09-03 18:20:00.000000

Adds:
- users.credential_version (int, default 1): bumped on every password
  change/reset; embedded in JWTs as `cver` so old tokens die immediately.
- users.must_change_password (bool, default false): backend-controlled flag
  set by an admin password reset; denies normal protected functionality
  until the user changes their password.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f9a1c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a663d2440b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'credential_version',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('1'),
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'must_change_password',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'credential_version')
