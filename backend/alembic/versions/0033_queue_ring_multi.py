"""TASK-023.10 -- QueueMember : sonnerie meme si occupe + autoriser plusieurs appels de file

Revision ID: 0033_queue_ring_multi
Revises: 0032_ring_group_members_s023_9
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0033_queue_ring_multi'
down_revision: Union[str, Sequence[str], None] = '0032_ring_group_members_s023_9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('queue_members', sa.Column('ring_even_if_busy', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('queue_members', sa.Column('allow_multiple_queue_calls', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('queue_members', 'allow_multiple_queue_calls')
    op.drop_column('queue_members', 'ring_even_if_busy')
