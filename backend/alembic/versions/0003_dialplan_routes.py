"""add outbound_routes and inbound_routes tables

Revision ID: 0003_dialplan
Revises: 0002_users
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0003_dialplan'
down_revision: Union[str, Sequence[str], None] = '0002_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'outbound_routes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('dial_patterns', sa.Text(), nullable=False),
        sa.Column('trunk_id', sa.UUID(), nullable=False),
        sa.Column('strip_digits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prepend_digits', sa.String(20), nullable=True),
        sa.Column('caller_id_override', sa.String(30), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asterisk_synced', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trunk_id'], ['sip_trunks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'inbound_routes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('did_id', sa.UUID(), nullable=True),
        sa.Column('did_number', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('destination_type', sa.String(20), nullable=False, server_default='extension'),
        sa.Column('destination', sa.String(100), nullable=False),
        sa.Column('schedule_id', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asterisk_synced', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['did_id'], ['tenant_dids.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('inbound_routes')
    op.drop_table('outbound_routes')
