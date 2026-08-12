"""TenantTemplate devient une bibliotheque par serveur (comme GlobalTemplate) +
choix explicite du template actif par compagnie/poste (TASK-S044.1)

Revision ID: 0047_template_explicit_selection
Revises: 0046_template_inheritance_chain
Create Date: 2026-08-03
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0047_template_explicit_selection'
down_revision: Union[str, Sequence[str], None] = '0046_template_inheritance_chain'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenant_templates devient une bibliotheque partagee par serveur (choisie
    # explicitement par compagnie), plus une donnee privee par compagnie.
    op.execute("DELETE FROM tenant_templates")
    op.drop_constraint('tenant_templates_tenant_id_fkey', 'tenant_templates', type_='foreignkey')
    op.drop_column('tenant_templates', 'tenant_id')
    op.add_column('tenant_templates', sa.Column('server_id', UUID(as_uuid=True), sa.ForeignKey('sipv_servers.id', ondelete='CASCADE'), nullable=False))

    op.add_column('tenants', sa.Column('selected_tenant_template_id', UUID(as_uuid=True), sa.ForeignKey('tenant_templates.id', ondelete='SET NULL'), nullable=True))
    op.add_column('provisioned_phones', sa.Column('selected_tenant_model_template_id', UUID(as_uuid=True), sa.ForeignKey('tenant_model_templates.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('provisioned_phones', 'selected_tenant_model_template_id')
    op.drop_column('tenants', 'selected_tenant_template_id')
    op.drop_column('tenant_templates', 'server_id')
    op.add_column('tenant_templates', sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False))
