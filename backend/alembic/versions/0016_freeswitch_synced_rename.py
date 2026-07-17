"""rename asterisk_synced to freeswitch_synced

Revision ID: 0016_freeswitch_synced_rename
Revises: 0015_audit_log
Create Date: 2026-07-17
"""
from typing import Union, Sequence
from alembic import op

revision: str = '0016_freeswitch_synced_rename'
down_revision: Union[str, Sequence[str], None] = '0015_audit_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('sip_extensions', 'asterisk_synced', new_column_name='freeswitch_synced')
    op.alter_column('sip_trunks', 'asterisk_synced', new_column_name='freeswitch_synced')


def downgrade() -> None:
    op.alter_column('sip_extensions', 'freeswitch_synced', new_column_name='asterisk_synced')
    op.alter_column('sip_trunks', 'freeswitch_synced', new_column_name='asterisk_synced')
