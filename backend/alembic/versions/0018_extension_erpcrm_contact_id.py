"""add erpcrm_contact_id to sip_extensions

Revision ID: 0018_extension_erpcrm_contact_id
Revises: 0017_extension_codec_schedule
Create Date: 2026-07-18
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0018_extension_erpcrm_contact_id'
down_revision: Union[str, Sequence[str], None] = '0017_extension_codec_schedule'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('erpcrm_contact_id', UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'erpcrm_contact_id')
