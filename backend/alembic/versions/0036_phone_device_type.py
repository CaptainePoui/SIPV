"""TASK-023.13 -- PhoneModel.device_type (telephone/ata/softphone/intercom)

Revision ID: 0036_phone_device_type
Revises: 0035_ring_detail
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0036_phone_device_type'
down_revision: Union[str, Sequence[str], None] = '0035_ring_detail'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('phone_models', sa.Column('device_type', sa.String(20), nullable=False, server_default='telephone'))


def downgrade() -> None:
    op.drop_column('phone_models', 'device_type')
