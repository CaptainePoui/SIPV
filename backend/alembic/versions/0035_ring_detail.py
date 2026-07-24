"""TASK-023.12 -- sonnerie detaillee (interne/externe/file/silencieuse/regles caller ID)

Revision ID: 0035_ring_detail
Revises: 0034_intercom_paging
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0035_ring_detail'
down_revision: Union[str, Sequence[str], None] = '0034_intercom_paging'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('ring_internal', sa.String(50), nullable=True))
    op.add_column('sip_extensions', sa.Column('ring_external', sa.String(50), nullable=True))
    op.add_column('sip_extensions', sa.Column('ring_queue', sa.String(50), nullable=True))
    op.add_column('sip_extensions', sa.Column('silent_ring', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('caller_id_ring_rules', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'caller_id_ring_rules')
    op.drop_column('sip_extensions', 'silent_ring')
    op.drop_column('sip_extensions', 'ring_queue')
    op.drop_column('sip_extensions', 'ring_external')
    op.drop_column('sip_extensions', 'ring_internal')
