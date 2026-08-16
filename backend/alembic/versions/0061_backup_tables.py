"""TASK-S059 : backup cloud automatique de notre propre infra SIPV (Dropbox/
Google Drive) -- PAS le stockage cloud client pour enregistrements d'appel
(TASK-S012.1, sujet distinct).

Revision ID: 0061_backup_tables
Revises: 0060_tenant_moh_shuffle
Create Date: 2026-08-15
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = '0061_backup_tables'
down_revision: Union[str, Sequence[str], None] = '0060_tenant_moh_shuffle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cloud_backup_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider', sa.String(20), nullable=False, unique=True),
        sa.Column('refresh_token_enc', sa.Text(), nullable=True),
        sa.Column('account_label', sa.String(255), nullable=True),
        sa.Column('client_id', sa.String(255), nullable=True),
        sa.Column('client_secret_enc', sa.Text(), nullable=True),
        sa.Column('oauth_state', sa.String(64), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='America/Toronto'),
        sa.Column('backup_hour', sa.String(5), nullable=False, server_default='02:00'),
        sa.Column('bandwidth_limit_kbps', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'backup_cycles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('frequency_type', sa.String(10), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('month_of_year', sa.Integer(), nullable=True),
        sa.Column('retention_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('retention_count', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'backup_run_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cycle_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('filename', sa.String(255), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('triggered_manually', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('backup_run_logs')
    op.drop_table('backup_cycles')
    op.drop_table('cloud_backup_connections')
