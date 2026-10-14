"""Touches Grandstream a leurs vrais codes + SIP Server en adresse IPv4 (2026-10-14, Philippe, photos de la page web du
poste 102 : touches melangees, « Information » / « Verrouillage clavier » en page 2, SIP Server = « sipv-lab »).

Cause (gabarit officiel 1.0.11.106, ~/GrandStream/Template_Config_Pcode) : la touche n etait ecrite a P23800+4(n-1),
alors que sur les GXP21xx les touches 1-6 sont P1363.../P1465... et P23800 est la touche 7 ; les touches dynamiques ont
leur propre legende de modes. Les codes de chaque touche sont maintenant calcules par provisioning.py (vpk_keys :
p_mode, p_account, p_label, p_value). P47 (SIP Server) = la meme adresse IPv4 que le proxy (interne ou publique) au lieu
du nom du serveur.

Revision ID: 0072_vpk_pcodes_by_model
Revises: 0071_internal_devices
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0072_vpk_pcodes_by_model'
down_revision: Union[str, Sequence[str], None] = '0071_internal_devices'
branch_labels = None
depends_on = None

OLD_KEYS = """{%- for k in vpk_keys %}
  <P{{ k.base }}>{{ k.mode }}</P{{ k.base }}>
  <P{{ k.base + 1 }}>{{ k.account }}</P{{ k.base + 1 }}>
  <P{{ k.base + 2 }}>{{ k.label }}</P{{ k.base + 2 }}>
  <P{{ k.base + 3 }}>{{ k.value }}</P{{ k.base + 3 }}>
{%- endfor %}"""
NEW_KEYS = """{%- for k in vpk_keys %}
  <P{{ k.p_mode }}>{{ k.mode }}</P{{ k.p_mode }}>
  <P{{ k.p_account }}>{{ k.account }}</P{{ k.p_account }}>
  <P{{ k.p_label }}>{{ k.label }}</P{{ k.p_label }}>
  <P{{ k.p_value }}>{{ k.value }}</P{{ k.p_value }}>
{%- endfor %}"""
OLD_P47 = "<P47>{{ server.hostname if server else '' }}</P47>"
NEW_P47 = "<P47>{{ sip_proxy_host }}</P47>"

SQL = "UPDATE phone_models SET config_template = replace(replace(config_template, :ok, :nk), :op, :np) WHERE config_template LIKE :l"


def upgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"ok": OLD_KEYS, "nk": NEW_KEYS, "op": OLD_P47, "np": NEW_P47, "l": "%k.base%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(SQL), {"ok": NEW_KEYS, "nk": OLD_KEYS, "op": NEW_P47, "np": OLD_P47, "l": "%k.p_mode%"})
