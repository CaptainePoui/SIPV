"""« Modele par defaut » (2026-10-14, comme l'UCM : « Default Model Template ») : phone_button_templates.is_default -- un
poste sans modele choisi prend le modele par defaut de sa compagnie pour son modele de telephone.

Revision ID: 0082_template_default
Revises: 0081_wallpapers
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0082_template_default'
down_revision: Union[str, Sequence[str], None] = '0081_wallpapers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('phone_button_templates', sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('phone_button_templates', 'is_default')
