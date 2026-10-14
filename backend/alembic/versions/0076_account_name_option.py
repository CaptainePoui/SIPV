"""Account Name (P270) reglable par poste (2026-10-14, test de Philippe sur le 102 : touches LINE 2-4 sans le nom du
compte -- gabarit officiel : une touche sans description affiche l'« Account Name », vide par defaut chez Grandstream).
Sans reglage du poste, rien ne change : P270 = nom du poste. P3 (nom envoye a l'appele) n'est pas touche.

Revision ID: 0076_account_name_option
Revises: 0075_phone_softkeys
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0076_account_name_option'
down_revision: Union[str, Sequence[str], None] = '0075_phone_softkeys'
branch_labels = None
depends_on = None

OLD = "<P270>{{ extension.name }}</P270>"
NEW = "<P270>{{ options.account_name if options.account_name is defined else extension.name }}</P270>"
SQL = "UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": OLD, "n": NEW, "l": "%<P270>{{ extension.name }}</P270>%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"o": NEW, "n": OLD, "l": "%options.account_name%"})
