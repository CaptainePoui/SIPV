"""Provisionnement (2026-10-10, Philippe : « 192.168.1.55 non, il faut que ce soit mon IP publique !!! des que je quitte le
bureau le local ne marche pas ») : le proxy SIP envoye aux telephones (P48 Grandstream) etait l'adresse privee du
serveur ; il devient SIPV_PUBLIC_IP ({{ sip_proxy_host }}) -- le port 5061 public mene a Kamailio, et ca marche aussi
au bureau (boucle NAT verifiee). Meme intention que le commentaire de SIPV_PUBLIC_IP dans config.py.

Revision ID: 0069_sip_proxy_public
Revises: 0068_provision_url_root
Create Date: 2026-10-10
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0069_sip_proxy_public'
down_revision: Union[str, Sequence[str], None] = '0068_provision_url_root'
branch_labels = None
depends_on = None

OLD = "<P48>{{ (server.ip_address if server and server.ip_address else (server.hostname if server else '')) }}</P48>"
NEW = "<P48>{{ sip_proxy_host }}</P48>"


def upgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"),
                          {"o": OLD, "n": NEW, "l": f"%{OLD}%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE phone_models SET config_template = replace(config_template, :n, :o) WHERE config_template LIKE :l"),
                          {"o": OLD, "n": NEW, "l": f"%{NEW}%"})
