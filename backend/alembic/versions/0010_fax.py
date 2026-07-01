"""add fax_lines and fax_jobs tables

Revision ID: 0010_fax
Revises: 0009_recordings
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0010_fax'
down_revision: Union[str, Sequence[str], None] = '0009_recordings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE fax_direction_enum AS ENUM ('inbound', 'outbound')")
    op.execute("CREATE TYPE fax_status_enum AS ENUM ('pending', 'processing', 'delivered', 'failed')")

    op.create_table(
        'fax_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('did_id', sa.UUID(), nullable=True),
        sa.Column('fax_number', sa.String(30), nullable=False),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('delivery_email', sa.String(255), nullable=True),
        sa.Column('use_t38', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ata_ip', sa.String(45), nullable=True),
        sa.Column('ata_model', sa.String(60), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['did_id'], ['tenant_dids.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'fax_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('fax_line_id', sa.UUID(), nullable=True),
        sa.Column('direction', sa.Enum('inbound', 'outbound', name='fax_direction_enum'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'delivered', 'failed', name='fax_status_enum'), nullable=False, server_default='pending'),
        sa.Column('remote_number', sa.String(30), nullable=True),
        sa.Column('pages', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('delivery_email', sa.String(255), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('asterisk_uniqueid', sa.String(150), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fax_line_id'], ['fax_lines.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fax_jobs_tenant_id', 'fax_jobs', ['tenant_id'])
    op.create_index('ix_fax_jobs_created_at', 'fax_jobs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_fax_jobs_created_at', table_name='fax_jobs')
    op.drop_index('ix_fax_jobs_tenant_id', table_name='fax_jobs')
    op.drop_table('fax_jobs')
    op.drop_table('fax_lines')
    op.execute("DROP TYPE fax_status_enum")
    op.execute("DROP TYPE fax_direction_enum")
