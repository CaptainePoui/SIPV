"""Touches programmables Grandstream (2026-10-11, Philippe, photos du GXP2135 du poste 102 : « je ne veux pas de page 2 ;
on a un moyen de les remettre a none et la provision se ferait bien, il enleverait le bouton ») : la configuration
n'envoyait que les touches definies -- un Grandstream garde ses anciens reglages pour tout ce qui n'est pas envoye
(page 2 : « Verrouillage… », « INFO », restes d'une ancienne configuration). Maintenant les 32 touches (4 pages de 8)
sont toujours envoyees, chacune a sa vraie position (page * 8 + position) ; une touche non definie = « aucune » (-1,
legende « Fixed VPK »). Liste calculee par provisioning.py (vpk_keys).

Revision ID: 0070_vpk_all_keys
Revises: 0069_sip_proxy_public
Create Date: 2026-10-11
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0070_vpk_all_keys'
down_revision: Union[str, Sequence[str], None] = '0069_sip_proxy_public'
branch_labels = None
depends_on = None

OLD = """{%- for b in buttons %}
{%- set base = 23800 + loop.index0 * 4 %}
  <P{{ base }}>{{ button_mode.get(b.button_type, -1) }}</P{{ base }}>
  <P{{ base + 1 }}>{{ b.sip_account_index - 1 }}</P{{ base + 1 }}>
  <P{{ base + 2 }}>{{ b.label or '' }}</P{{ base + 2 }}>
  <P{{ base + 3 }}>{{ b.value or b.destination or '' }}</P{{ base + 3 }}>
{%- endfor %}"""
NEW = """{%- for k in vpk_keys %}
  <P{{ k.base }}>{{ k.mode }}</P{{ k.base }}>
  <P{{ k.base + 1 }}>{{ k.account }}</P{{ k.base + 1 }}>
  <P{{ k.base + 2 }}>{{ k.label }}</P{{ k.base + 2 }}>
  <P{{ k.base + 3 }}>{{ k.value }}</P{{ k.base + 3 }}>
{%- endfor %}"""


def upgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE phone_models SET config_template = replace(config_template, :o, :n) WHERE config_template LIKE :l"),
                          {"o": OLD, "n": NEW, "l": "%loop.index0 * 4%"})


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE phone_models SET config_template = replace(config_template, :n, :o) WHERE config_template LIKE :l"),
                          {"o": OLD, "n": NEW, "l": "%vpk_keys%"})
