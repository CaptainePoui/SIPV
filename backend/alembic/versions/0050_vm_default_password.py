"""NIP par defaut des nouvelles boites vocales, configurable (TASK-S023.33)

Revision ID: 0050_vm_default_password
Revises: 0049_template_multi_select
Create Date: 2026-08-04
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0050_vm_default_password'
down_revision: Union[str, Sequence[str], None] = '0049_template_multi_select'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('telephony_settings', sa.Column('voicemail_default_password', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('telephony_settings', 'voicemail_default_password')
