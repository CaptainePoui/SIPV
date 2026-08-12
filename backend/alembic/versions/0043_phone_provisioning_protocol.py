"""TASK-023.31 -- protocole de provisioning du poste (reseau)

Revision ID: 0043_phone_provisioning_protocol
Revises: 0042_vm_skip_instructions
Create Date: 2026-07-25
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0043_phone_provisioning_protocol'
down_revision: Union[str, Sequence[str], None] = '0042_vm_skip_instructions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'provisioned_phones',
        sa.Column('provisioning_protocol', sa.String(10), nullable=False, server_default='https'),
    )


def downgrade() -> None:
    op.drop_column('provisioned_phones', 'provisioning_protocol')
