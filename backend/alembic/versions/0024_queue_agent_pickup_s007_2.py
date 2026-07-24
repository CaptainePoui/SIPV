"""TASK-S007.2 -- queue_members: champs agent ; sip_extensions: pickup/paging/interception

Revision ID: 0024_queue_agent_s007_2
Revises: 0023_security_s014_2
Create Date: 2026-07-23
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0024_queue_agent_s007_2'
down_revision: Union[str, Sequence[str], None] = '0023_security_s014_2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('queue_members', sa.Column('agent_number', sa.String(length=20), nullable=True))
    op.add_column('queue_members', sa.Column('agent_password', sa.String(length=50), nullable=True))
    op.add_column('queue_members', sa.Column('is_dynamic', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('queue_members', sa.Column('auto_login', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('queue_members', sa.Column('pause_allowed', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('queue_members', sa.Column('pause_reasons', sa.String(length=255), nullable=True))
    op.add_column('queue_members', sa.Column('wrap_up_time_seconds', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('queue_members', sa.Column('skills', sa.String(length=255), nullable=True))

    op.add_column('sip_extensions', sa.Column('pickup_group', sa.String(length=50), nullable=True))
    op.add_column('sip_extensions', sa.Column('paging_groups', sa.String(length=255), nullable=True))
    op.add_column('sip_extensions', sa.Column('can_intercept_calls', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'can_intercept_calls')
    op.drop_column('sip_extensions', 'paging_groups')
    op.drop_column('sip_extensions', 'pickup_group')

    op.drop_column('queue_members', 'skills')
    op.drop_column('queue_members', 'wrap_up_time_seconds')
    op.drop_column('queue_members', 'pause_reasons')
    op.drop_column('queue_members', 'pause_allowed')
    op.drop_column('queue_members', 'auto_login')
    op.drop_column('queue_members', 'is_dynamic')
    op.drop_column('queue_members', 'agent_password')
    op.drop_column('queue_members', 'agent_number')
