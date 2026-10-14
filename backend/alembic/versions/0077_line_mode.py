"""Key Mode = Line Mode (P8369=1) toujours envoye au GXP21xx (2026-10-14) : la regle des touches Ligne (la 1re avec le nom,
les suivantes sans nom sur le compte 2 non configure, pour les appels suivants -- prouvee sur le 102) depend du Line Mode ;
un telephone laisse en Account Mode garderait le sien. Valeur par defaut du gabarit officiel (« Key Mode. 1 - Line Mode,
2 - Account Mode. Default is 1 »).

Revision ID: 0077_line_mode
Revises: 0076_account_name_option
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0077_line_mode'
down_revision: Union[str, Sequence[str], None] = '0076_account_name_option'
branch_labels = None
depends_on = None

OLD = "  <P1362>{{ options.language }}</P1362>"
NEW = OLD + "\n  <P8369>1</P8369>"
SQL = "UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": OLD, "n": NEW, "l": "%k.p_mode%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": NEW, "n": OLD, "l": "%<P8369>1</P8369>%"})
