"""TASK-032.2 (TASKERPCRM.md) : retention CDR configurable par tenant, 1 an
par defaut, augmentable manuellement si un client paie pour la ressource.

Revision ID: 0062_cdr_retention
Revises: 0061_backup_tables
Create Date: 2026-08-19
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0062_cdr_retention'
down_revision: Union[str, Sequence[str], None] = '0061_backup_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('cdr_retention_days', sa.Integer(), nullable=False, server_default='365'))


def downgrade() -> None:
    op.drop_column('tenants', 'cdr_retention_days')
