"""Options des telephones Grandstream par modele (TASK-051, 2026-10-14) : catalogue genere a partir du gabarit officiel du
fabricant par tools/parse_gs_template.py (sections, options, libelles, choix, valeurs par defaut). Philippe : comme l'UCM,
on ajoute au modele seulement les options voulues ; tout le reste garde la valeur par defaut du telephone.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

CATALOG_DIR = Path(__file__).parent / "catalogs"
MODEL_CATALOG = {m: "gxp21xx_1.0.11.106.json" for m in ("GXP2130", "GXP2135", "GXP2140", "GXP2160", "GXP2170")}

# Calcules par SIPV a partir du poste et du serveur (ou par les editeurs de touches / boutons sous l'ecran / fond d'ecran) :
# affiches dans l'arbre mais pas modifiables dans un modele.
MANAGED = {
    "P271": "compte actif", "P270": "nom du compte", "P47": "serveur SIP", "P48": "proxy", "P35": "utilisateur SIP",
    "P36": "identifiant d'authentification", "P34": "mot de passe SIP", "P3": "nom affiché", "P130": "transport SIP",
    "P2329": "SIPS", "P99": "messagerie", "P212": "protocole de provisionnement", "P237": "serveur de configuration",
    "P95030": "redémarrage à distance", "P8369": "mode des touches (règle des lignes)", "P26015": "remise à zéro à distance",
    "P2916": "fond d'écran", "P2917": "fond d'écran",
}
PCODE = re.compile(r"^P\d+$")


@lru_cache(maxsize=8)
def _load(name: str) -> dict:
    return json.loads((CATALOG_DIR / name).read_text(encoding="utf-8"))


def option_catalog(model_name: str | None) -> dict | None:
    name = MODEL_CATALOG.get((model_name or "").upper())
    if not name:
        return None
    data = _load(name)
    return {"source": data.get("source"), "sections": data["sections"], "managed": MANAGED}


def to_pcodes(options: dict | None) -> dict:
    """Options d'un modele / d'un poste -> {« P1362 »: valeur}. Accepte l'ancienne cle « language » (= P1362)."""
    out: dict = {}
    for k, v in (options or {}).items():
        if k == "language":
            out.setdefault("P1362", str(v))
        elif PCODE.match(k) and v is not None:
            out[k] = str(v)
    return out


def managed_in(options: dict | None) -> list[str]:
    return sorted(k for k in to_pcodes(options) if k in MANAGED)
