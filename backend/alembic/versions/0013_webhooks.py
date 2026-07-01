"""add webhook_endpoints and webhook_deliveries tables

Revision ID: 0013_webhooks
Revises: 0012_security
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0013_webhooks'
down_revision: Union[str, Sequence[str], None] = '0012_security'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_endpoints',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(100), nullable=True),
        sa.Column('event_types', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('endpoint_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(60), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['endpoint_id'], ['webhook_endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_deliveries_success', 'webhook_deliveries', ['success'])
    op.create_index('ix_webhook_deliveries_next_retry', 'webhook_deliveries', ['next_retry_at'])


def downgrade() -> None:
    op.drop_index('ix_webhook_deliveries_next_retry', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_success', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_endpoints')
