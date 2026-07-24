"""TASK-S011.2 -- provisioned_phones: fiche physique du poste

Revision ID: 0021_phone_physical
Revises: 0020_extension_s018_3
Create Date: 2026-07-23
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0021_phone_physical'
down_revision: Union[str, Sequence[str], None] = '0020_extension_s018_3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('provisioned_phones', sa.Column('serial_number', sa.String(length=60), nullable=True))
    op.add_column('provisioned_phones', sa.Column('hardware_version', sa.String(length=30), nullable=True))
    op.add_column('provisioned_phones', sa.Column('encrypted_admin_password', sa.Text(), nullable=True))
    op.add_column('provisioned_phones', sa.Column('wifi_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('provisioned_phones', sa.Column('bluetooth_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('provisioned_phones', sa.Column('headset_used', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('provisioned_phones', sa.Column('expansion_module', sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column('provisioned_phones', 'expansion_module')
    op.drop_column('provisioned_phones', 'headset_used')
    op.drop_column('provisioned_phones', 'bluetooth_enabled')
    op.drop_column('provisioned_phones', 'wifi_enabled')
    op.drop_column('provisioned_phones', 'encrypted_admin_password')
    op.drop_column('provisioned_phones', 'hardware_version')
    op.drop_column('provisioned_phones', 'serial_number')
