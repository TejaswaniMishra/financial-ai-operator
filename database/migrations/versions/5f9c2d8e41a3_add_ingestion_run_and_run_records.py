"""add ingestion run and run record tables, link records to runs

Revision ID: 5f9c2d8e41a3
Revises: 7a6c6a68e443
Create Date: 2026-09-04 13:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f9c2d8e41a3'
down_revision: Union[str, Sequence[str], None] = '7a6c6a68e443'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Durable, auditable ingestion batch (M13).
    op.create_table('ingestion_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('batch_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('total_records', sa.Integer(), nullable=False),
        sa.Column('successful_records', sa.Integer(), nullable=False),
        sa.Column('duplicate_records', sa.Integer(), nullable=False),
        sa.Column('rejected_records', sa.Integer(), nullable=False),
        sa.Column('failed_records', sa.Integer(), nullable=False),
        sa.Column('error_summary', sa.String(length=1000), nullable=True),
        sa.Column('created_by', sa.String(length=64), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ingestion_runs_batch_fingerprint', 'ingestion_runs', ['batch_fingerprint'], unique=True)

    # Row-level outcomes per source record (M13).
    op.create_table('ingestion_run_records',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('row_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['ingestion_runs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ingestion_run_records_run_id', 'ingestion_run_records', ['run_id'], unique=False)
    op.create_index('ix_ing_run_rec_run_status', 'ingestion_run_records', ['run_id', 'status'], unique=False)

    # Lineage: link existing ingestion records to the run that produced them.
    # SQLite cannot ALTER constraints outside batch (copy-and-move) mode.
    with op.batch_alter_table('ingestion_records') as batch_op:
        batch_op.add_column(sa.Column('run_id', sa.String(), nullable=True))
        batch_op.create_foreign_key(
            'fk_ingestion_records_run_id', 'ingestion_runs', ['run_id'], ['id']
        )
        batch_op.create_index('ix_ingestion_records_run_id', ['run_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ingestion_records_run_id', table_name='ingestion_records')
    # SQLite cannot ALTER constraints; use batch mode to drop the column.
    with op.batch_alter_table('ingestion_records') as batch_op:
        batch_op.drop_column('run_id')
    op.drop_index('ix_ing_run_rec_run_status', table_name='ingestion_run_records')
    op.drop_index('ix_ingestion_run_records_run_id', table_name='ingestion_run_records')
    op.drop_table('ingestion_run_records')
    op.drop_index('ix_ingestion_runs_batch_fingerprint', table_name='ingestion_runs')
    op.drop_table('ingestion_runs')
