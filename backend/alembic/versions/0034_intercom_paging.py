"""TASK-023.11 -- intercom/paging granulaire (tonalite, micro coupe, multicast, volume force)

Revision ID: 0034_intercom_paging
Revises: 0033_queue_ring_multi
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0034_intercom_paging'
down_revision: Union[str, Sequence[str], None] = '0033_queue_ring_multi'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('intercom_warning_tone', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sip_extensions', sa.Column('intercom_mic_muted_on_answer', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('paging_priority', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('sip_extensions', sa.Column('paging_allow_send', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sip_extensions', sa.Column('paging_allow_receive', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sip_extensions', sa.Column('paging_emergency', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('multicast_address', sa.String(45), nullable=True))
    op.add_column('sip_extensions', sa.Column('multicast_port', sa.Integer(), nullable=True))
    op.add_column('sip_extensions', sa.Column('forced_volume', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'forced_volume')
    op.drop_column('sip_extensions', 'multicast_port')
    op.drop_column('sip_extensions', 'multicast_address')
    op.drop_column('sip_extensions', 'paging_emergency')
    op.drop_column('sip_extensions', 'paging_allow_receive')
    op.drop_column('sip_extensions', 'paging_allow_send')
    op.drop_column('sip_extensions', 'paging_priority')
    op.drop_column('sip_extensions', 'intercom_mic_muted_on_answer')
    op.drop_column('sip_extensions', 'intercom_warning_tone')
