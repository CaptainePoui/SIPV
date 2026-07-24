"""TASK-023.23 -- paging groups (bidirectionnel/unidirectionnel, multicast)

Revision ID: 0040_paging_groups
Revises: 0039_seed_grandstream
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0040_paging_groups'
down_revision: Union[str, Sequence[str], None] = '0039_seed_grandstream'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'paging_groups',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('extension', sa.String(20), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False, server_default='unidirectional'),
        sa.Column('multicast_address', sa.String(45), nullable=True),
        sa.Column('multicast_port', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_table(
        'paging_group_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('paging_group_id', UUID(as_uuid=True), sa.ForeignKey('paging_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extension_id', UUID(as_uuid=True), sa.ForeignKey('sip_extensions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('can_send', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_receive', sa.Boolean(), nullable=False, server_default='true'),
    )


def downgrade() -> None:
    op.drop_table('paging_group_members')
    op.drop_table('paging_groups')
