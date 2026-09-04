"""add mfa fields and recovery codes table

Revision ID: 9c3e7a5b2d6f
Revises: 8a2c1d4f6e5b
Create Date: 2026-09-04

Adds mfa_secret_encrypted / mfa_enabled to users plus the one-time
MFA recovery-code table (SHA-256 hashes only).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c3e7a5b2d6f"
down_revision: Union[str, None] = "8a2c1d4f6e5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mfa_secret_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_mfa_recovery_user_hash",
        "mfa_recovery_codes",
        ["user_id", "code_hash"],
        unique=True,
    )
    op.create_index(
        "ix_mfa_recovery_codes_user_id",
        "mfa_recovery_codes",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mfa_recovery_codes_user_id", table_name="mfa_recovery_codes")
    op.drop_index("ix_mfa_recovery_user_hash", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret_encrypted")
