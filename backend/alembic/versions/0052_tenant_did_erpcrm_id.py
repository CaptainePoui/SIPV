"""ERPCRM devient maitre pour les DID (numero/destination/succursale) --
TenantDID gagne erpcrm_did_id pour retrouver/mettre a jour la copie
synchronisee (TASK-S010.5).

Revision ID: 0052_tenant_did_erpcrm_id
Revises: 0051_e911_erpcrm_site_id
Create Date: 2026-08-05
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0052_tenant_did_erpcrm_id'
down_revision: Union[str, Sequence[str], None] = '0051_e911_erpcrm_site_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenant_dids', sa.Column('erpcrm_did_id', UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint('uq_tenant_dids_erpcrm_did_id', 'tenant_dids', ['erpcrm_did_id'])


def downgrade() -> None:
    op.drop_constraint('uq_tenant_dids_erpcrm_did_id', 'tenant_dids', type_='unique')
    op.drop_column('tenant_dids', 'erpcrm_did_id')
