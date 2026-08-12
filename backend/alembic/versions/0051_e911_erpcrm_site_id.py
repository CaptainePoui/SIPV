"""ERPCRM devient maitre pour les succursales (company_sites) -- E911Address
gagne erpcrm_site_id pour retrouver/mettre a jour la copie synchronisee.

Revision ID: 0051_e911_erpcrm_site_id
Revises: 0050_vm_default_password
Create Date: 2026-08-05
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0051_e911_erpcrm_site_id'
down_revision: Union[str, Sequence[str], None] = '0050_vm_default_password'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('e911_addresses', sa.Column('erpcrm_site_id', UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint('uq_e911_addresses_erpcrm_site_id', 'e911_addresses', ['erpcrm_site_id'])


def downgrade() -> None:
    op.drop_constraint('uq_e911_addresses_erpcrm_site_id', 'e911_addresses', type_='unique')
    op.drop_column('e911_addresses', 'erpcrm_site_id')
