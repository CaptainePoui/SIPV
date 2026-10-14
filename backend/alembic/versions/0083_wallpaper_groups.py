"""Un fond d'ecran = une image avec une version par taille d'ecran (2026-10-14, Philippe : « on choisit le background,
recadrer ou crop sont des options de gestion apres ; tu mets un background inadequat pour le modele ») :
wallpapers.group_id. Donnees : chaque fond existant devient son propre groupe ; les deux « Simple IP » Global (320x240 et
480x272) forment un seul fond.

Revision ID: 0083_wallpaper_groups
Revises: 0082_template_default
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = '0083_wallpaper_groups'
down_revision: Union[str, Sequence[str], None] = '0082_template_default'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('wallpapers', sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_wallpapers_group_id', 'wallpapers', ['group_id'])
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE wallpapers SET group_id = id"))
    # memes nom et compte = un seul fond (ses versions par taille)
    bind.execute(sa.text("""UPDATE wallpapers w SET group_id = g.first_id FROM (
        SELECT coalesce(account_number, '') AS acct, name, (array_agg(id ORDER BY resolution))[1] AS first_id
        FROM wallpapers GROUP BY coalesce(account_number, ''), name) g
        WHERE coalesce(w.account_number, '') = g.acct AND w.name = g.name"""))


def downgrade() -> None:
    op.drop_index('ix_wallpapers_group_id', 'wallpapers')
    op.drop_column('wallpapers', 'group_id')
