"""TASK-S033.2 : ordre de lecture du MOH par tenant -- aleatoire (defaut,
comportement historique) ou liste dans l'ordre choisi.

Revision ID: 0060_tenant_moh_shuffle
Revises: 0059_moh
Create Date: 2026-08-12
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0060_tenant_moh_shuffle'
down_revision: Union[str, Sequence[str], None] = '0059_moh'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('moh_shuffle', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('tenants', 'moh_shuffle')
