"""Templates choisissables en PLUSIEURS a la fois (TASK-S044.2) -- demande de
Philippe : "je dois pouvoir en choisir plusieurs... celui par defaut et un
autre qui ajoute l'oreillette et l'autre qui ajoute des boutons de park".
Convertit les FK simples (un seul choix) en tableaux UUID (plusieurs choix,
fusionnes dans l'ordre du tableau -- le dernier gagne en cas de conflit).

Revision ID: 0049_template_multi_select
Revises: 0048_seed_more_brands
Create Date: 2026-08-03
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from alembic import op

revision: str = '0049_template_multi_select'
down_revision: Union[str, Sequence[str], None] = '0048_seed_more_brands'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenants : selected_tenant_template_id (FK simple) -> selected_tenant_template_ids
    # (tableau, sans contrainte FK -- Postgres ne supporte pas de FK sur un
    # element de tableau, integrite geree cote application comme
    # blocked_countries/blocked_prefixes deja dans ce projet).
    op.add_column('tenants', sa.Column('selected_tenant_template_ids', ARRAY(UUID(as_uuid=True)), nullable=False, server_default='{}'))
    op.execute("UPDATE tenants SET selected_tenant_template_ids = ARRAY[selected_tenant_template_id] WHERE selected_tenant_template_id IS NOT NULL")
    op.drop_constraint('tenants_selected_tenant_template_id_fkey', 'tenants', type_='foreignkey')
    op.drop_column('tenants', 'selected_tenant_template_id')

    # tenants : nouveau -- Global Templates supplementaires choisis explicitement
    # par la compagnie, en plus de celui marque is_default (qui reste automatique).
    op.add_column('tenants', sa.Column('selected_global_template_ids', ARRAY(UUID(as_uuid=True)), nullable=False, server_default='{}'))

    # provisioned_phones : meme conversion pour le template par modele.
    op.add_column('provisioned_phones', sa.Column('selected_tenant_model_template_ids', ARRAY(UUID(as_uuid=True)), nullable=False, server_default='{}'))
    op.execute("UPDATE provisioned_phones SET selected_tenant_model_template_ids = ARRAY[selected_tenant_model_template_id] WHERE selected_tenant_model_template_id IS NOT NULL")
    op.drop_constraint('provisioned_phones_selected_tenant_model_template_id_fkey', 'provisioned_phones', type_='foreignkey')
    op.drop_column('provisioned_phones', 'selected_tenant_model_template_id')


def downgrade() -> None:
    op.add_column('provisioned_phones', sa.Column('selected_tenant_model_template_id', UUID(as_uuid=True), sa.ForeignKey('tenant_model_templates.id', ondelete='SET NULL')))
    op.execute("UPDATE provisioned_phones SET selected_tenant_model_template_id = selected_tenant_model_template_ids[1] WHERE array_length(selected_tenant_model_template_ids, 1) > 0")
    op.drop_column('provisioned_phones', 'selected_tenant_model_template_ids')

    op.drop_column('tenants', 'selected_global_template_ids')

    op.add_column('tenants', sa.Column('selected_tenant_template_id', UUID(as_uuid=True), sa.ForeignKey('tenant_templates.id', ondelete='SET NULL')))
    op.execute("UPDATE tenants SET selected_tenant_template_id = selected_tenant_template_ids[1] WHERE array_length(selected_tenant_template_ids, 1) > 0")
    op.drop_column('tenants', 'selected_tenant_template_ids')
