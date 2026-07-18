"""add sms_configs and sms_messages tables

Revision ID: 0011_sms
Revises: 0010_fax
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0011_sms'
down_revision: Union[str, Sequence[str], None] = '0010_fax'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sms_configs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.Enum('twilio', 'bandwidth', 'telnyx', 'sinch', 'vonage', 'other', name='sms_provider_enum'), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('api_secret', sa.Text(), nullable=True),
        sa.Column('account_sid', sa.String(100), nullable=True),
        sa.Column('from_number', sa.String(30), nullable=True),
        sa.Column('webhook_url', sa.String(255), nullable=True),
        sa.Column('monthly_limit', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id'),
    )

    op.create_table(
        'sms_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('direction', sa.Enum('inbound', 'outbound', name='sms_direction_enum'), nullable=False),
        sa.Column('status', sa.Enum('queued', 'sent', 'delivered', 'failed', 'received', name='sms_status_enum'), nullable=False, server_default='queued'),
        sa.Column('from_number', sa.String(30), nullable=False),
        sa.Column('to_number', sa.String(30), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('provider_message_id', sa.String(150), nullable=True),
        sa.Column('provider', sa.String(20), nullable=True),
        sa.Column('num_segments', sa.Integer(), nullable=True),
        sa.Column('cost', sa.String(20), nullable=True),
        sa.Column('error_code', sa.String(30), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sms_messages_tenant_id', 'sms_messages', ['tenant_id'])
    op.create_index('ix_sms_messages_created_at', 'sms_messages', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_sms_messages_created_at', table_name='sms_messages')
    op.drop_index('ix_sms_messages_tenant_id', table_name='sms_messages')
    op.drop_table('sms_messages')
    op.drop_table('sms_configs')
    op.execute("DROP TYPE sms_status_enum")
    op.execute("DROP TYPE sms_direction_enum")
    op.execute("DROP TYPE sms_provider_enum")
