"""add codec and schedule_id to sip_extensions

Revision ID: 0017_extension_codec_schedule
Revises: 0016_freeswitch_synced_rename
Create Date: 2026-07-17
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0017_extension_codec_schedule'
down_revision: Union[str, Sequence[str], None] = '0016_freeswitch_synced_rename'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('codec', sa.String(10), nullable=True))
    op.add_column('sip_extensions', sa.Column('schedule_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_sip_extensions_schedule_id', 'sip_extensions', 'schedules',
        ['schedule_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_sip_extensions_schedule_id', 'sip_extensions', type_='foreignkey')
    op.drop_column('sip_extensions', 'schedule_id')
    op.drop_column('sip_extensions', 'codec')
