"""TASK-023.6 -- typer les destinations de renvoi (poste/BV/externe/groupe/file/IVR/message)

Revision ID: 0031_forward_destination_types
Revises: 0030_caller_id_split_s018_6
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0031_forward_destination_types'
down_revision: Union[str, Sequence[str], None] = '0030_caller_id_split_s018_6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('forward_immediate_destination_type', sa.String(20), nullable=False, server_default='extension'))
    op.add_column('sip_extensions', sa.Column('forward_busy_destination_type', sa.String(20), nullable=False, server_default='extension'))
    op.add_column('sip_extensions', sa.Column('forward_no_answer_destination_type', sa.String(20), nullable=False, server_default='voicemail'))
    op.add_column('sip_extensions', sa.Column('forward_offline_destination_type', sa.String(20), nullable=False, server_default='voicemail'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'forward_offline_destination_type')
    op.drop_column('sip_extensions', 'forward_no_answer_destination_type')
    op.drop_column('sip_extensions', 'forward_busy_destination_type')
    op.drop_column('sip_extensions', 'forward_immediate_destination_type')
