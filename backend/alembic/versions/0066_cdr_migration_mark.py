"""TASK-051 (TASKERPCRM, 2026-10-10) : migration de tenant -- l'historique d'appels d'un poste ou d'un numero migre
reste dans l'ancien tenant, marque (date de migration, tenant de destination) au lieu d'etre supprime. Demande de
Philippe : « il peut aussi tout garder et juste mettre une espece de date de fin ou de migration dans les CDR ».

Revision ID: 0066_cdr_migration_mark
Revises: 0065_park_timeout_mode
Create Date: 2026-10-10
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = '0066_cdr_migration_mark'
down_revision: Union[str, Sequence[str], None] = '0065_park_timeout_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cdr', sa.Column('migrated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cdr', sa.Column('migrated_to_tenant_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_cdr_migrated_to_tenant', 'cdr', 'tenants', ['migrated_to_tenant_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_cdr_migrated_to_tenant', 'cdr', type_='foreignkey')
    op.drop_column('cdr', 'migrated_to_tenant_id')
    op.drop_column('cdr', 'migrated_at')
