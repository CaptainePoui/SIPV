"""Boutons sous l'ecran en P-codes (2026-10-14) : le gabarit officiel les a en P-codes (« Settings/Programmable Keys /
Softkeys Settings » : P2923 = disposition personnalisee, P2925... = un etat chacun) -- plus d'elements « alias » melanges
au fichier P-codes (0073), dont l'acceptation par le telephone n'etait pas prouvee.

Revision ID: 0079_softkeys_pcodes
Revises: 0078_allow_sip_reset
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0079_softkeys_pcodes'
down_revision: Union[str, Sequence[str], None] = '0078_allow_sip_reset'
branch_labels = None
depends_on = None

OLD = """{%- for name, value in softkey_items %}
  <item name="{{ name }}">{{ value|e }}</item>
{%- endfor %}"""
NEW = """{%- for p, value in softkey_items %}
  <P{{ p }}>{{ value|e }}</P{{ p }}>
{%- endfor %}"""
SQL = "UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": OLD, "n": NEW, "l": "%softkey_items%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": NEW, "n": OLD, "l": "%softkey_items%"})
