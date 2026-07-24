"""TASK-023.25 -- templates de configuration de boutons (sauvegarder/appliquer)

Revision ID: 0041_button_templates
Revises: 0040_paging_groups
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0041_button_templates'
down_revision: Union[str, Sequence[str], None] = '0040_paging_groups'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'phone_button_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_table(
        'phone_button_template_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('template_id', UUID(as_uuid=True), sa.ForeignKey('phone_button_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('button_type', sa.String(30), nullable=False),
        sa.Column('label', sa.String(60), nullable=True),
        sa.Column('value', sa.String(100), nullable=True),
        sa.Column('destination', sa.String(100), nullable=True),
        sa.Column('sip_account_index', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('client_editable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('locked_by_simpleip', sa.Boolean(), nullable=False, server_default='true'),
    )


def downgrade() -> None:
    op.drop_table('phone_button_template_items')
    op.drop_table('phone_button_templates')
