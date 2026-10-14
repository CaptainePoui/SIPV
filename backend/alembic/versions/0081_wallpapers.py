"""Fonds d'ecran des telephones (2026-10-14, Philippe : fonds lies aux compagnies, Global = fond de tous les telephones ;
importer, cadrer fit / crop selon le modele). Table wallpapers (liee par numero de compte, vide = Global), choix dans le
modele de provisionnement et dans le poste. Gabarit GXP2135 : P2916 = 1 « Download » + P2917 = adresse de l'image
(gabarit officiel « Wallpaper Source » / « Wallpaper Server Path »), envoyes seulement si un fond s'applique.

Revision ID: 0081_wallpapers
Revises: 0080_options_pcodes
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = '0081_wallpapers'
down_revision: Union[str, Sequence[str], None] = '0080_options_pcodes'
branch_labels = None
depends_on = None

OLD = """{%- for p, value in extra_pcodes %}
  <P{{ p }}>{{ value|e }}</P{{ p }}>
{%- endfor %}"""
NEW = OLD + """
{%- if wallpaper_url %}
  <P2916>1</P2916>
  <P2917>{{ wallpaper_url|e }}</P2917>
{%- endif %}"""
SQL = "UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.create_table(
        'wallpapers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('account_number', sa.String(20), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('resolution', sa.String(12), nullable=False),
        sa.Column('mode', sa.String(10), nullable=False, server_default='crop'),
        sa.Column('crop', sa.JSON(), nullable=True),
        sa.Column('original_name', sa.String(200), nullable=True),
        sa.Column('has_original', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_wallpapers_account_number', 'wallpapers', ['account_number'])
    op.add_column('phone_button_templates', sa.Column('wallpaper_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('wallpapers.id', ondelete='SET NULL'), nullable=True))
    op.add_column('provisioned_phones', sa.Column('wallpaper_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('wallpapers.id', ondelete='SET NULL'), nullable=True))
    op.get_bind().execute(sa.text(SQL), {"o": OLD, "n": NEW, "l": "%extra_pcodes%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": NEW, "n": OLD, "l": "%wallpaper_url%"})
    op.drop_column('provisioned_phones', 'wallpaper_id')
    op.drop_column('phone_button_templates', 'wallpaper_id')
    op.drop_index('ix_wallpapers_account_number', 'wallpapers')
    op.drop_table('wallpapers')
