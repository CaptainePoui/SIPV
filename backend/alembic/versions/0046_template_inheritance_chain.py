"""Global/Tenant/Model templates -- chaine d'heritage a 5 niveaux du catalogue
d'options (TASK-S044, item 1 de TASK-S043/TASK-027)

Revision ID: 0046_template_inheritance_chain
Revises: 0045_gxp2135_provisioning
Create Date: 2026-08-02
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0046_template_inheritance_chain'
down_revision: Union[str, Sequence[str], None] = '0045_gxp2135_provisioning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'global_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('server_id', UUID(as_uuid=True), sa.ForeignKey('sipv_servers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'tenant_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'tenant_model_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phone_model_id', UUID(as_uuid=True), sa.ForeignKey('phone_models.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('tenant_model_templates')
    op.drop_table('tenant_templates')
    op.drop_table('global_templates')
