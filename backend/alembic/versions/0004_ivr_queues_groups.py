"""add ivr, queues, ring_groups, parking_lots tables

Revision ID: 0004_ivr
Revises: 0003_dialplan
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0004_ivr'
down_revision: Union[str, Sequence[str], None] = '0003_dialplan'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ivrs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('greeting_text', sa.Text(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('invalid_destination', sa.String(100), nullable=True),
        sa.Column('timeout_destination', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'ivr_options',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ivr_id', sa.UUID(), nullable=False),
        sa.Column('digit', sa.String(5), nullable=False),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('destination_type', sa.String(20), nullable=False),
        sa.Column('destination', sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(['ivr_id'], ['ivrs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'queues',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('queue_name', sa.String(100), nullable=False),
        sa.Column('strategy', sa.String(20), nullable=False, server_default='rrmemory'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('no_answer_destination', sa.String(100), nullable=True),
        sa.Column('max_wait_seconds', sa.Integer(), nullable=False, server_default='120'),
        sa.Column('announce_hold_time', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('music_on_hold', sa.String(50), nullable=False, server_default='default'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_name'),
    )

    op.create_table(
        'queue_members',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('queue_id', sa.UUID(), nullable=False),
        sa.Column('extension_username', sa.String(100), nullable=False),
        sa.Column('penalty', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'ring_groups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('extension', sa.String(20), nullable=False),
        sa.Column('ring_strategy', sa.String(20), nullable=False, server_default='simultaneous'),
        sa.Column('ring_time', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('members', sa.Text(), nullable=False),
        sa.Column('no_answer_destination', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'parking_lots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('park_extension', sa.String(10), nullable=False, server_default='700'),
        sa.Column('parking_slots_start', sa.Integer(), nullable=False, server_default='701'),
        sa.Column('parking_slots_end', sa.Integer(), nullable=False, server_default='720'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='120'),
        sa.Column('return_extension', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('parking_lots')
    op.drop_table('ring_groups')
    op.drop_table('queue_members')
    op.drop_table('queues')
    op.drop_table('ivr_options')
    op.drop_table('ivrs')
