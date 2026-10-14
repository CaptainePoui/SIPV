"""Options du telephone dans le modele de provisionnement (2026-10-14, Philippe : « la langue est dans le template, c'est
toutes des templates par modele ») : phone_button_templates.options. Les postes prennent : valeurs Simple IP -> modele ->
ajustements du poste. Les anciens niveaux (templates de tenant, templates par modele, options par defaut de la compagnie
pour l'ecran) ne sont plus lus ; leurs tables restent en place jusqu'a confirmation (rien n'est efface ici).

Revision ID: 0074_template_options
Revises: 0073_provisioning_templates
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0074_template_options'
down_revision: Union[str, Sequence[str], None] = '0073_provisioning_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('phone_button_templates', sa.Column('options', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('phone_button_templates', 'options')
