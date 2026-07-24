"""TASK-023.17 -- boutons/touches programmables (editeur en liste, sans attendre la photo)

Revision ID: 0038_phone_buttons
Revises: 0037_ext_identification
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0038_phone_buttons'
down_revision: Union[str, Sequence[str], None] = '0037_ext_identification'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'phone_buttons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('provisioned_phone_id', UUID(as_uuid=True), sa.ForeignKey('provisioned_phones.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('button_type', sa.String(30), nullable=False),
        sa.Column('label', sa.String(60), nullable=True),
        sa.Column('value', sa.String(100), nullable=True),
        sa.Column('destination', sa.String(100), nullable=True),
        sa.Column('sip_account_index', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('client_editable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('locked_by_simpleip', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('phone_buttons')
