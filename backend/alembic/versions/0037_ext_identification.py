"""TASK-023.14 -- langue d'affichage, fuseau horaire, nom independant du contact

Revision ID: 0037_ext_identification
Revises: 0036_phone_device_type
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0037_ext_identification'
down_revision: Union[str, Sequence[str], None] = '0036_phone_device_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('display_language', sa.String(5), nullable=False, server_default='fr'))
    op.add_column('sip_extensions', sa.Column('timezone', sa.String(50), nullable=True))
    op.add_column('sip_extensions', sa.Column('name_override', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'name_override')
    op.drop_column('sip_extensions', 'timezone')
    op.drop_column('sip_extensions', 'display_language')
