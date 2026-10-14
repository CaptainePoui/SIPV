"""Options du telephone en P-codes (2026-10-14, Philippe : comme l'UCM, on ajoute au modele les options voulues, tout le
reste par defaut) : le gabarit GXP2135 lit les reglages Simple IP qu'il fixait en dur dans les options (repli = valeur
actuelle) et ajoute a la fin les autres options choisies (extra_pcodes). Donnees : l'ancienne cle « language » devient
P1362 (son vrai P-code, gabarit officiel « Display Language ») dans les modeles, les postes et les valeurs par defaut du
serveur ; valeurs par defaut du serveur : keep-alive (P52 = 2 « keep alive », P84 = 20 s, demande de Philippe).

Revision ID: 0080_options_pcodes
Revises: 0079_softkeys_pcodes
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import json
import sqlalchemy as sa
from alembic import op

revision: str = '0080_options_pcodes'
down_revision: Union[str, Sequence[str], None] = '0079_softkeys_pcodes'
branch_labels = None
depends_on = None

FIXED = [("P32", "60"), ("P40", "5060"), ("P138", "20"), ("P26002", "1200"), ("P30", "pool.ntp.org"),
         ("P8333", "1.pool.ntp.org"), ("P64", "EST5EDT"), ("P246", "EST+5EDT+4,M3.2.0,M11.1.0")]
PAIRS = [(f"<{p}>{v}</{p}>", f"<{p}>{{{{ pcodes.get('{p}', '{v}') }}}}</{p}>") for p, v in FIXED]
PAIRS.append(("<P1362>{{ options.language }}</P1362>", "<P1362>{{ pcodes.get('P1362', 'auto') }}</P1362>"))
PAIRS.append(("  <P26015>1</P26015>", "  <P26015>1</P26015>\n{%- for p, value in extra_pcodes %}\n  <P{{ p }}>{{ value|e }}</P{{ p }}>\n{%- endfor %}"))
TABLES = [("phone_button_templates", "options"), ("provisioned_phones", "extra_config"), ("global_templates", "options")]
KEEPALIVE = {"P52": "2", "P84": "20"}


def _rewrite(bind, forward: bool) -> None:
    rows = bind.execute(sa.text("SELECT id, config_template FROM phone_models WHERE config_template LIKE '%k.p_mode%'")).all()
    for rid, text in rows:
        for old, new in PAIRS:
            text = text.replace(old, new) if forward else text.replace(new, old)
        bind.execute(sa.text("UPDATE phone_models SET config_template = :t WHERE id = :i"), {"t": text, "i": rid})


def _data(bind, forward: bool) -> None:
    for table, col in TABLES:
        for rid, val in bind.execute(sa.text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")).all():
            if val is None or val == "null":
                continue                                          # JSON « null » : rien a convertir
            d = dict(val if isinstance(val, dict) else json.loads(val))
            if forward and "language" in d:
                d["P1362"] = d.pop("language")
            elif not forward and "P1362" in d:
                d["language"] = d.pop("P1362")
            if table == "global_templates":
                is_default = bind.execute(sa.text("SELECT is_default FROM global_templates WHERE id = :i"), {"i": rid}).scalar()
                if is_default:
                    for k, v in KEEPALIVE.items():
                        if forward:
                            d.setdefault(k, v)
                        elif d.get(k) == v:
                            d.pop(k)
            bind.execute(sa.text(f"UPDATE {table} SET {col} = CAST(:v AS json) WHERE id = :i"), {"v": json.dumps(d), "i": rid})


def upgrade() -> None:
    bind = op.get_bind()
    _rewrite(bind, True)
    _data(bind, True)


def downgrade() -> None:
    bind = op.get_bind()
    _rewrite(bind, False)
    _data(bind, False)
