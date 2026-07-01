"""add recording_policies and call_recordings tables

Revision ID: 0009_recordings
Revises: 0008_provisioning
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0009_recordings'
down_revision: Union[str, Sequence[str], None] = '0008_provisioning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE storage_backend_enum AS ENUM ('local', 'dropbox', 'onedrive', 's3')")

    op.create_table(
        'recording_policies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('record_inbound', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('record_outbound', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('record_internal', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('storage_backend', sa.Enum('local', 'dropbox', 'onedrive', 's3', name='storage_backend_enum'), nullable=False, server_default='local'),
        sa.Column('storage_path', sa.String(255), nullable=True),
        sa.Column('storage_credentials', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id'),
    )

    op.create_table(
        'call_recordings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('cdr_id', sa.UUID(), nullable=True),
        sa.Column('uniqueid', sa.String(150), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('storage_backend', sa.String(20), nullable=False, server_default='local'),
        sa.Column('storage_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(10), nullable=True),
        sa.Column('caller', sa.String(80), nullable=True),
        sa.Column('callee', sa.String(80), nullable=True),
        sa.Column('direction', sa.String(10), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cdr_id'], ['cdr.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recordings_tenant_id', 'call_recordings', ['tenant_id'])
    op.create_index('ix_recordings_started_at', 'call_recordings', ['started_at'])


def downgrade() -> None:
    op.drop_index('ix_recordings_started_at', table_name='call_recordings')
    op.drop_index('ix_recordings_tenant_id', table_name='call_recordings')
    op.drop_table('call_recordings')
    op.drop_table('recording_policies')
    op.execute("DROP TYPE storage_backend_enum")
