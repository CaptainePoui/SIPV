"""add transport to sip_extensions

Revision ID: 0019_extension_transport
Revises: 0018_extension_erpcrm_contact_id
Create Date: 2026-07-18
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0019_extension_transport'
down_revision: Union[str, Sequence[str], None] = '0018_extension_erpcrm_contact_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('transport', sa.String(length=10), nullable=False, server_default='tls'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'transport')
