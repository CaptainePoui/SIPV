"""TASK-023.4 -- enregistrement automatique granulaire (interne/externe x entrant/sortant)

Revision ID: 0028_record_categories
Revises: 0027_fwd_offline_enabled
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0028_record_categories'
down_revision: Union[str, Sequence[str], None] = '0027_fwd_offline_enabled'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('record_internal_incoming', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('record_internal_outgoing', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('record_external_incoming', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('record_external_outgoing', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'record_external_outgoing')
    op.drop_column('sip_extensions', 'record_external_incoming')
    op.drop_column('sip_extensions', 'record_internal_outgoing')
    op.drop_column('sip_extensions', 'record_internal_incoming')
