"""TASK-023.4 -- ajoute forward_offline_enabled pour symetrie avec les 3 autres renvois

Revision ID: 0027_fwd_offline_enabled
Revises: 0026_encrypt_extension_passwords
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0027_fwd_offline_enabled'
down_revision: Union[str, Sequence[str], None] = '0026_encrypt_extension_passwords'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('forward_offline_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'forward_offline_enabled')
