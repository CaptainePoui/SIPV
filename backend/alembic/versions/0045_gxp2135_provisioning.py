"""TASK-S011.5 -- catalogue GXP2135 individuel + config_template reel + options telephonie

Separe la ligne catalogue combinee "GXP2130/40/60/70/35" en modeles individuels
(TASK-023.18) -- on garde le meme id de ligne pour GXP2135 (renommage) pour ne
pas casser un ProvisionedPhone deja provisionne dessus, et on ajoute 4 nouvelles
lignes vides (GXP2130/2140/2160/2170, sans config_template pour l'instant --
seul le GXP2135 est en ligne aujourd'hui pour les tests). Ajoute aussi
Tenant.phone_option_defaults (JSON, defauts compagnie du catalogue d'options).

Gabarit Jinja2 ecrit pour ce projet -- structure/P-codes guides par le fichier
ScopServ reel fourni par l'utilisateur et par la doc officielle Grandstream
gxp2130_40_60_70_35_config_1.0.11.106.txt, mais aucune valeur (mot de passe,
numero, nom client) n'est copiee : tout vient de la DB via Jinja2.

Revision ID: 0045_gxp2135_provisioning
Revises: 0044_sipv_servers
Create Date: 2026-08-02
"""
from typing import Union, Sequence
import uuid
import sqlalchemy as sa
from alembic import op

revision: str = '0045_gxp2135_provisioning'
down_revision: Union[str, Sequence[str], None] = '0044_sipv_servers'
branch_labels = None
depends_on = None

NEW_MODELS = ["GXP2130", "GXP2140", "GXP2160", "GXP2170"]

CONFIG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
<gs_provision version="1">
 <mac>{{ mac }}</mac>
 <config version="1">
{%- if extension %}
  <P271>1</P271>
  <P270>{{ extension.name }}</P270>
  <P47>{{ server.hostname if server else '' }}</P47>
  <P48>{{ (server.ip_address if server and server.ip_address else (server.hostname if server else '')) }}</P48>
  <P35>{{ extension.username }}</P35>
  <P36>{{ extension.username }}</P36>
  <P34>{{ ext_password }}</P34>
  <P3>{{ extension.name }}</P3>
  <P32>60</P32>
  <P40>5060</P40>
  <P138>20</P138>
  <P26002>1200</P26002>
  <P130>{{ {'udp': 0, 'tcp': 1, 'tls': 2}.get(extension.transport, 2) }}</P130>
  <P2329>{{ 1 if extension.transport == 'tls' else 0 }}</P2329>
  <P99>{{ 1 if extension.voicemail_enabled else 0 }}</P99>
{%- endif %}
  <P212>{{ {'tftp': 0, 'http': 1, 'https': 2, 'ftp': 3, 'ftps': 4}.get(phone.provisioning_protocol, 2) }}</P212>
  <P237>{{ config_host }}/api/v1/provisioning/{{ phone.id }}/config</P237>
  <P95030>1</P95030>
  <P30>pool.ntp.org</P30>
  <P8333>1.pool.ntp.org</P8333>
  <P64>EST5EDT</P64>
  <P246>EST+5EDT+4,M3.2.0,M11.1.0</P246>
  <P1362>{{ options.language }}</P1362>
{%- for b in buttons %}
{%- set base = 23800 + loop.index0 * 4 %}
  <P{{ base }}>{{ button_mode.get(b.button_type, -1) }}</P{{ base }}>
  <P{{ base + 1 }}>{{ b.sip_account_index - 1 }}</P{{ base + 1 }}>
  <P{{ base + 2 }}>{{ b.label or '' }}</P{{ base + 2 }}>
  <P{{ base + 3 }}>{{ b.value or b.destination or '' }}</P{{ base + 3 }}>
{%- endfor %}
 </config>
</gs_provision>
"""


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column('tenants', sa.Column('phone_option_defaults', sa.JSON(), nullable=True))

    conn.execute(
        sa.text(
            "UPDATE phone_models SET model = 'GXP2135', config_template = :tmpl "
            "WHERE brand = 'Grandstream' AND model = 'GXP2130/40/60/70/35'"
        ),
        {"tmpl": CONFIG_TEMPLATE},
    )
    for model in NEW_MODELS:
        conn.execute(
            sa.text(
                "INSERT INTO phone_models (id, brand, model, firmware_version, device_type, "
                "max_accounts, provisioning_protocol, is_active, created_at) "
                "VALUES (:id, 'Grandstream', :model, '1.0.11.106', 'telephone', 1, 'https', true, now())"
            ),
            {"id": str(uuid.uuid4()), "model": model},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM phone_models WHERE brand = 'Grandstream' AND model = ANY(:models)"), {"models": NEW_MODELS})
    conn.execute(
        sa.text(
            "UPDATE phone_models SET model = 'GXP2130/40/60/70/35', config_template = NULL "
            "WHERE brand = 'Grandstream' AND model = 'GXP2135'"
        )
    )
    op.drop_column('tenants', 'phone_option_defaults')
