"""Remise a zero a distance (2026-10-14, Philippe : « je veux l'option Factory Reset avec un popup Attention ») : le GXP21xx
accepte la remise a zero par NOTIFY « Event: reset » authentifie seulement si « Allow SIP Reset » = Oui (P26015, compte 1,
« Default is 0 » dans le gabarit officiel ; guide d'administration : « When the phone receives the NOTIFY with event:
RESET, the phone should perform a factory reset after the authentication »). Toujours envoye a 1.

Revision ID: 0078_allow_sip_reset
Revises: 0077_line_mode
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0078_allow_sip_reset'
down_revision: Union[str, Sequence[str], None] = '0077_line_mode'
branch_labels = None
depends_on = None

OLD = "  <P8369>1</P8369>"
NEW = OLD + "\n  <P26015>1</P26015>"
SQL = "UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": OLD, "n": NEW, "l": "%<P8369>1</P8369>%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": NEW, "n": OLD, "l": "%<P26015>1</P26015>%"})
