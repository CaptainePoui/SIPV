"""TASK-S033 : musique d'attente (MOH) -- bibliotheque MohFile (tenant_id
nullable = global) + selection multiple par tenant (TenantMohSelection).

Revision ID: 0059_moh
Revises: 0058_server_sip_channel_ips
Create Date: 2026-08-08
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0059_moh'
down_revision: Union[str, Sequence[str], None] = '0058_server_sip_channel_ips'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'moh_files',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'tenant_moh_selections',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('moh_file_id', UUID(as_uuid=True), sa.ForeignKey('moh_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('tenant_moh_selections')
    op.drop_table('moh_files')
