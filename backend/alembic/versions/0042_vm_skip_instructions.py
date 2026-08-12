"""TASK-023.29 -- boite vocale : sauter les instructions parlees natives

Revision ID: 0042_vm_skip_instructions
Revises: 0041_button_templates
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0042_vm_skip_instructions'
down_revision: Union[str, Sequence[str], None] = '0041_button_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'voicemail_boxes',
        sa.Column('skip_instructions', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('voicemail_boxes', 'skip_instructions')
