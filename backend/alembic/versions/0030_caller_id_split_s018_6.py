"""TASK-018.6 -- caller ID separe interne/externe + masquer + defaut compagnie

Revision ID: 0030_caller_id_split_s018_6
Revises: 0029_call_permission_s018_5
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0030_caller_id_split_s018_6'
down_revision: Union[str, Sequence[str], None] = '0029_call_permission_s018_5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('caller_id_internal_name', sa.String(100), nullable=True))
    op.add_column('sip_extensions', sa.Column('caller_id_internal_number', sa.String(30), nullable=True))
    op.add_column('sip_extensions', sa.Column('caller_id_external_name', sa.String(100), nullable=True))
    op.add_column('sip_extensions', sa.Column('caller_id_external_number', sa.String(30), nullable=True))
    op.add_column('sip_extensions', sa.Column('hide_caller_id', sa.Boolean(), nullable=False, server_default='false'))

    op.add_column('tenants', sa.Column('default_caller_id_name', sa.String(100), nullable=True))
    op.add_column('tenants', sa.Column('default_caller_id_number', sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'default_caller_id_number')
    op.drop_column('tenants', 'default_caller_id_name')

    op.drop_column('sip_extensions', 'hide_caller_id')
    op.drop_column('sip_extensions', 'caller_id_external_number')
    op.drop_column('sip_extensions', 'caller_id_external_name')
    op.drop_column('sip_extensions', 'caller_id_internal_number')
    op.drop_column('sip_extensions', 'caller_id_internal_name')
