"""add security_events, acl_rules, fraud_rules, blocked_ips tables

Revision ID: 0012_security
Revises: 0011_sms
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0012_security'
down_revision: Union[str, Sequence[str], None] = '0011_sms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'security_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.String(40), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False, server_default='info'),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_security_events_tenant_id', 'security_events', ['tenant_id'])
    op.create_index('ix_security_events_created_at', 'security_events', ['created_at'])
    op.create_index('ix_security_events_event_type', 'security_events', ['event_type'])

    op.create_table(
        'acl_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('cidr', sa.String(50), nullable=False),
        sa.Column('action', sa.String(5), nullable=False),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'fraud_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('max_calls_per_hour', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_calls', sa.Integer(), nullable=True),
        sa.Column('max_international_calls_per_day', sa.Integer(), nullable=True),
        sa.Column('block_international', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('block_premium', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_email', sa.String(255), nullable=True),
        sa.Column('auto_block_on_alert', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id'),
    )

    op.create_table(
        'blocked_ips',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.Column('block_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ip_address'),
    )


def downgrade() -> None:
    op.drop_table('blocked_ips')
    op.drop_table('fraud_rules')
    op.drop_table('acl_rules')
    op.drop_index('ix_security_events_event_type', table_name='security_events')
    op.drop_index('ix_security_events_created_at', table_name='security_events')
    op.drop_index('ix_security_events_tenant_id', table_name='security_events')
    op.drop_table('security_events')
