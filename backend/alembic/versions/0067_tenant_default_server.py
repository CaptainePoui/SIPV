"""TASK-051 (ERPCRM, 2026-10-10) : un tenant cree par ERPCRM (sync/company) n'avait aucun serveur (server_id vide) --
le provisionnement des telephones prend l'adresse SIP du serveur du tenant (P47/P48 Grandstream), la configuration
sortait donc sans serveur (constate sur T1000 apres la migration des postes 100-103). Tant qu'il n'existe qu'un seul
serveur actif, chaque tenant sans serveur y est rattache (meme regle que le backfill de TASK-S042).

Revision ID: 0067_tenant_default_server
Revises: 0066_cdr_migration_mark
Create Date: 2026-10-10
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0067_tenant_default_server'
down_revision: Union[str, Sequence[str], None] = '0066_cdr_migration_mark'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    servers = conn.execute(sa.text("SELECT id FROM sipv_servers WHERE is_active")).scalars().all()
    if len(servers) == 1:
        conn.execute(sa.text("UPDATE tenants SET server_id = :s WHERE server_id IS NULL"), {"s": servers[0]})


def downgrade() -> None:
    pass   # rattachement voulu : on ne remet pas un tenant sans serveur
