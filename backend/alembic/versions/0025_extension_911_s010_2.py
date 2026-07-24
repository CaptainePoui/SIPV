"""TASK-S010.2 -- 911 par poste (pas seulement par DID)

Revision ID: 0025_extension_911_s010_2
Revises: 0024_queue_agent_s007_2
Create Date: 2026-07-23
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0025_extension_911_s010_2'
down_revision: Union[str, Sequence[str], None] = '0024_queue_agent_s007_2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'extension_911_assignments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extension_id', UUID(as_uuid=True), sa.ForeignKey('sip_extensions.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('e911_address_id', UUID(as_uuid=True), sa.ForeignKey('e911_addresses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('emergency_location', sa.String(length=200), nullable=True),
        sa.Column('floor', sa.String(length=20), nullable=True),
        sa.Column('office', sa.String(length=50), nullable=True),
        sa.Column('alert_email', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('extension_911_assignments')
