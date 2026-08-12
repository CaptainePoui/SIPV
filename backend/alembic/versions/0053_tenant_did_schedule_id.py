"""Horaire (Time Condition) sur TenantDID -- un seul DID peut avoir un
horaire (Schedule) au lieu de dupliquer le DID par plage horaire
(TASK-S016/S010.7, demande Philippe 2026-08-06).

Revision ID: 0053_tenant_did_schedule_id
Revises: 0052_tenant_did_erpcrm_id
Create Date: 2026-08-06
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0053_tenant_did_schedule_id'
down_revision: Union[str, Sequence[str], None] = '0052_tenant_did_erpcrm_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenant_dids', sa.Column('schedule_id', UUID(as_uuid=True), sa.ForeignKey('schedules.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('tenant_dids', 'schedule_id')
