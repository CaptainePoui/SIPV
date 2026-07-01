"""add schedules, schedule_rules, holidays tables

Revision ID: 0014_schedules
Revises: 0013_webhooks
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0014_schedules'
down_revision: Union[str, Sequence[str], None] = '0013_webhooks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'schedules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='America/Montreal'),
        sa.Column('closed_destination_type', sa.String(20), nullable=True),
        sa.Column('closed_destination', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'schedule_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('schedule_id', sa.UUID(), nullable=False),
        sa.Column('days_of_week', sa.String(20), nullable=False, server_default='0,1,2,3,4'),
        sa.Column('open_time', sa.Time(), nullable=False),
        sa.Column('close_time', sa.Time(), nullable=False),
        sa.Column('label', sa.String(60), nullable=True),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'holidays',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('override_destination_type', sa.String(20), nullable=True),
        sa.Column('override_destination', sa.String(100), nullable=True),
        sa.Column('recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_holidays_tenant_date', 'holidays', ['tenant_id', 'date'])


def downgrade() -> None:
    op.drop_index('ix_holidays_tenant_date', table_name='holidays')
    op.drop_table('holidays')
    op.drop_table('schedule_rules')
    op.drop_table('schedules')
