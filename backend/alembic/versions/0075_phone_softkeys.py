"""Boutons sous l'ecran personnalises par poste (2026-10-14, Philippe : onglet « Provisionnement » du poste, chaque
reglage du modele avec une case « Modele » ; decochee = personnalise) : provisioned_phones.softkeys (disposition par etat
d'appel qui remplace celle du modele pour ce poste).

Revision ID: 0075_phone_softkeys
Revises: 0074_template_options
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0075_phone_softkeys'
down_revision: Union[str, Sequence[str], None] = '0074_template_options'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('provisioned_phones', sa.Column('softkeys', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('provisioned_phones', 'softkeys')
