"""Modeles de provisionnement par modele de telephone (2026-10-14, Philippe : « pourquoi je ne peux pas le creer ici ?
c'est LA place ! pas de doublon ; dans le poste on choisit le modele qu'on veut, ceux disponibles pour le modele de
telephone ») : phone_button_templates.phone_model_id / pages / softkeys ; provisioned_phones.button_template_id (lien,
pas copie). Gabarit GXP2135 : boutons sous l'ecran (elements « alias » du gabarit officiel) envoyes quand le poste a un
modele.

Revision ID: 0073_provisioning_templates
Revises: 0072_vpk_pcodes_by_model
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = '0073_provisioning_templates'
down_revision: Union[str, Sequence[str], None] = '0072_vpk_pcodes_by_model'
branch_labels = None
depends_on = None

KEYS_END = """  <P{{ k.p_value }}>{{ k.value }}</P{{ k.p_value }}>
{%- endfor %}"""
SOFTKEYS = KEYS_END + """
{%- for name, value in softkey_items %}
  <item name="{{ name }}">{{ value|e }}</item>
{%- endfor %}"""
SQL = "UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.add_column('phone_button_templates', sa.Column('phone_model_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('phone_models.id', ondelete='SET NULL'), nullable=True))
    op.add_column('phone_button_templates', sa.Column('pages', sa.Integer(), server_default='1', nullable=False))
    op.add_column('phone_button_templates', sa.Column('softkeys', sa.JSON(), nullable=True))
    op.add_column('provisioned_phones', sa.Column('button_template_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('phone_button_templates.id', ondelete='SET NULL'), nullable=True))
    op.get_bind().execute(sa.text(SQL), {"o": KEYS_END, "n": SOFTKEYS, "l": "%k.p_value%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": SOFTKEYS, "n": KEYS_END, "l": "%softkey_items%"})
    op.drop_column('provisioned_phones', 'button_template_id')
    op.drop_column('phone_button_templates', 'softkeys')
    op.drop_column('phone_button_templates', 'pages')
    op.drop_column('phone_button_templates', 'phone_model_id')
