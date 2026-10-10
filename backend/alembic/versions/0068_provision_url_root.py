"""Provisionnement Grandstream (2026-10-10, TASK-051 cote ERPCRM) : P237 (adresse du serveur de configuration) pointait
vers « {SIPV_HOST}:8020/api/v1/provisioning/<id>/config » alors que P212 = HTTPS et que le port 8020 ne parle que HTTP :
apres un premier provisionnement, toutes les verifications suivantes echouaient. P237 = l'adresse du serveur seulement
({{ provision_host }}) : le telephone demande « /cfg<mac> » (standard Grandstream) au serveur web, qui le renvoie a SIPV
(/api/v1/provisioning/gs/cfg<mac>).

Revision ID: 0068_provision_url_root
Revises: 0067_tenant_default_server
Create Date: 2026-10-10
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0068_provision_url_root'
down_revision: Union[str, Sequence[str], None] = '0067_tenant_default_server'
branch_labels = None
depends_on = None

OLD = "<P237>{{ config_host }}/api/v1/provisioning/{{ phone.id }}/config</P237>"
NEW = "<P237>{{ provision_host }}</P237>"


def upgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE phone_models SET config_template = replace(config_template, :o, :n) "
                                  "WHERE config_template LIKE :l"), {"o": OLD, "n": NEW, "l": f"%{OLD}%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE phone_models SET config_template = replace(config_template, :n, :o) "
                                  "WHERE config_template LIKE :l"), {"o": OLD, "n": NEW, "l": f"%{NEW}%"})
