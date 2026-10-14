"""Migration de tenant (TASK-051 cote ERPCRM, 2026-10-10).

Deplace des postes et des numeros d'un tenant a un autre (une succursale qui se joint a une autre compagnie ou la
quitte, des postes d'essai...). Ecran : ERPCRM -> Serveur -> Migration ; c'est le technicien qui choisit tout.

Regles de Philippe :
- il choisit les postes et les numeros qui partent ;
- chaque groupe (et ce qu'il contient) : deplacer, copier (les deux restent actifs : l'ancien sans les postes partis,
  le nouveau avec eux) ou laisser (les postes partis en sont retires) -- meme choix pour parcage, IVR, files,
  interphone, interception, horaires, messages enregistres, musique d'attente, trunks et routes, jours feries ;
- le poste / le numero garde son adresse 911 (Philippe, 2026-10-14 : « si le poste migre rien ne change ») ; l'adresse
  passe au tenant d'arrivee quand plus rien ne l'utilise dans celui de depart, et toutes celles du tenant de depart y
  passent quand il est vide (une succursale qui entre dans le tenant de sa maison mere) ;
- tenant d'arrivee pas encore cree (maison mere sans telephonie) : l'apercu le traite comme un tenant vide
  (dest_new_account_number) ; ERPCRM le cree juste avant l'execution ;
- l'historique d'appels reste dans l'ancien tenant, marque (date de migration, tenant de destination).

Toujours un apercu d'abord (preview) ; l'execution refait l'apercu, refuse s'il reste un conflit, copie la base,
puis fait tout dans une seule transaction. Apres : avis de facturation (retrait / ajout) vers ERPCRM, flux de musique
d'attente regeneres, telephones des postes migres reprovisionnes (redemarrage), XML recharge.
Limite connue : les messages vocaux deja recus restent dans la boite de l'ancien tenant (fichiers de FreeSWITCH) --
signale dans l'apercu.
"""
import logging
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select, delete, update, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.default_parking import default_numbers, ensure_default_parking, has_parking
from app.models.cdr import CDR
from app.models.dialplan import OutboundRoute, InboundRoute
from app.models.e911 import E911Address, DID911Assignment, ExtensionE911Assignment
from app.models.ivr import (IVR, IVROption, Queue, QueueMember, RingGroup, RingGroupMember, RingGroupFailoverStep,
                            ParkingLot, PagingGroup, PagingGroupMember)
from app.models.moh import MohFile, TenantMohSelection
from app.models.prompt import AudioPrompt
from app.models.provisioning import ProvisionedPhone
from app.models.schedule import Schedule, ScheduleRule, Holiday
from app.models.sip import SIPExtension, SIPTrunk, TenantDID, PickupGroup
from app.models.tenant import Tenant
from app.models.voicemail import VoicemailBox, VoicemailMessage

log = logging.getLogger("tenant_migration")

PROMPT_DIR = Path(settings.APP_DIR) / "backend/uploads/audio_prompts"
MOH_DIR = Path(settings.APP_DIR) / "backend/uploads/moh_files"
BACKUP_DIR = Path.home() / "migration_backups"

# Sortes d'objets « avec un choix » : (cle, modele, libelle, copiable). Le parcage n'en fait pas partie : chaque tenant a
# sa propre zone, la destination en recoit une si elle n'en a pas, la source garde la sienne (TASK-051, 2026-10-11).
KINDS = [
    ("ring_groups", RingGroup, "Groupe d'appel", True),
    ("queues", Queue, "File d'attente", True),
    ("paging_groups", PagingGroup, "Groupe d'interphone", True),
    ("pickup_groups", PickupGroup, "Groupe d'interception", True),
    ("ivrs", IVR, "IVR", True),
    ("schedules", Schedule, "Horaire", True),
    ("prompts", AudioPrompt, "Message enregistré", True),
    ("moh", TenantMohSelection, "Musique d'attente", True),
    ("trunks", SIPTrunk, "Trunk (ligne vers le fournisseur)", False),   # copier = deux enregistrements du meme compte
    ("outbound_routes", OutboundRoute, "Route sortante", False),
    ("holidays", Holiday, "Jour férié", True),
]
MODELS = {k: m for k, m, _, _ in KINDS}
LABELS = {k: l for k, _, l, _ in KINDS}
COPYABLE = {k for k, _, _, c in KINDS if c}


def _name(kind: str, o) -> str:
    if kind == "moh":
        return "Sélection de musique d'attente"
    if kind == "holidays":
        return f"{o.name} ({o.date})"
    if kind == "outbound_routes":
        return o.name
    if kind in ("ring_groups", "paging_groups"):
        return f"{o.name} ({o.extension})"
    return getattr(o, "name", None) or str(o.id)


async def _tenant(db: AsyncSession, tid) -> Tenant | None:
    return await db.get(Tenant, uuid.UUID(str(tid))) if tid else None


def _new_tenant(account_number: str | None) -> Tenant | None:
    """Tenant d'arrivee qui n'existe pas encore : vide, pour l'apercu seulement (jamais ajoute a la base)."""
    return Tenant(id=uuid.uuid4(), account_number=account_number, company_name=account_number, is_active=True) if account_number else None


async def inventory(db: AsyncSession, tenant_id) -> dict:
    """Tout ce que le tenant contient, pour l'ecran (cases a cocher et choix)."""
    t = await _tenant(db, tenant_id)
    if not t:
        return {}
    exts = (await db.execute(select(SIPExtension).where(SIPExtension.tenant_id == t.id).order_by(SIPExtension.extension))).scalars().all()
    phones = {p.extension_id: p for p in (await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.tenant_id == t.id))).scalars().all()}
    vm_counts = dict((await db.execute(select(VoicemailBox.extension_id, func.count(VoicemailMessage.id))
                                       .join(VoicemailMessage, VoicemailMessage.mailbox_id == VoicemailBox.id)
                                       .where(VoicemailBox.tenant_id == t.id).group_by(VoicemailBox.extension_id))).all())
    e911 = {a.id: a for a in (await db.execute(select(E911Address).where(E911Address.tenant_id == t.id))).scalars().all()}
    ext_911 = {a.extension_id: a.e911_address_id for a in (await db.execute(select(ExtensionE911Assignment).where(ExtensionE911Assignment.tenant_id == t.id))).scalars().all()}
    did_911 = {a.did_id: a.e911_address_id for a in (await db.execute(select(DID911Assignment).where(DID911Assignment.tenant_id == t.id))).scalars().all()}
    dids = (await db.execute(select(TenantDID).where(TenantDID.tenant_id == t.id).order_by(TenantDID.number))).scalars().all()

    def addr(aid):
        a = e911.get(aid)
        return {"id": str(a.id), "label": a.label, "erpcrm_site_id": str(a.erpcrm_site_id) if a.erpcrm_site_id else None,
                "text": f"{a.civic_number} {a.street_name}, {a.city}"} if a else None

    out = {
        "tenant": {"id": str(t.id), "account_number": t.account_number, "company_name": t.company_name},
        "extensions": [{"id": str(e.id), "extension": e.extension, "name": e.name, "username": e.username, "is_active": e.is_active,
                        "phone": bool(phones.get(e.id)), "voicemail_messages": vm_counts.get(e.id, 0), "e911": addr(ext_911.get(e.id)),
                        "erpcrm_contact_id": str(e.erpcrm_contact_id) if e.erpcrm_contact_id else None} for e in exts],
        "dids": [{"id": str(d.id), "number": d.number, "label": d.label, "destination_type": d.destination_type,
                  "destination": d.destination, "erpcrm_did_id": str(d.erpcrm_did_id) if d.erpcrm_did_id else None,
                  "e911": addr(did_911.get(d.id))} for d in dids],
        "e911_addresses": [addr(a) for a in e911],
        "objects": {},
    }
    by_id = {e.id: e for e in exts}
    for kind, model, label, copyable in KINDS:
        rows = (await db.execute(select(model).where(model.tenant_id == t.id))).scalars().all()
        items = []
        for o in rows:
            members = []
            if kind == "ring_groups":
                members = [by_id[m.extension_id].extension for m in (await db.execute(select(RingGroupMember).where(RingGroupMember.ring_group_id == o.id))).scalars().all() if m.extension_id in by_id]
            elif kind == "paging_groups":
                members = [by_id[m.extension_id].extension for m in (await db.execute(select(PagingGroupMember).where(PagingGroupMember.paging_group_id == o.id))).scalars().all() if m.extension_id in by_id]
            elif kind == "queues":
                members = [m.extension_username for m in (await db.execute(select(QueueMember).where(QueueMember.queue_id == o.id))).scalars().all()]
            elif kind == "pickup_groups":
                members = [e.extension for e in exts if e.pickup_group == o.name]
            elif kind == "moh":
                f = await db.get(MohFile, o.moh_file_id)
                members = [f.name if f else "?"]
            items.append({"id": str(o.id), "name": _name(kind, o), "members": members})
        if items:
            out["objects"][kind] = {"label": label, "copyable": copyable, "items": items}
    return out


# ── Apercu ───────────────────────────────────────────────────────────────────

def _uuid(x):
    return uuid.UUID(str(x))


async def _plan(db: AsyncSession, sel: dict) -> dict:
    """Calcule tout ce que la migration fera. Retourne aussi les objets charges pour l'execution."""
    steps, conflicts, warnings = [], [], []
    src = await _tenant(db, sel.get("source_tenant_id"))
    dst = await _tenant(db, sel.get("dest_tenant_id")) if sel.get("dest_tenant_id") else _new_tenant(sel.get("dest_new_account_number"))
    if not src or not dst:
        return {"steps": [], "conflicts": ["Tenant de départ ou d'arrivée introuvable."], "warnings": [], "ctx": None}
    if src.id == dst.id:
        return {"steps": [], "conflicts": ["Le tenant d'arrivée doit être différent du tenant de départ."], "warnings": [], "ctx": None}
    if not dst.is_active:
        conflicts.append(f"Le tenant d'arrivée {dst.account_number} est désactivé.")

    actions = {k: {_uuid(i): a for i, a in (sel.get("objects", {}).get(k) or {}).items()} for k in MODELS}
    ext_sel = {_uuid(e["id"]): (e.get("new_number") or "").strip() for e in sel.get("extensions", [])}
    did_ids = {_uuid(d) for d in sel.get("dids", [])}

    exts = {e.id: e for e in (await db.execute(select(SIPExtension).where(SIPExtension.id.in_(ext_sel)))).scalars().all()}
    dids = {d.id: d for d in (await db.execute(select(TenantDID).where(TenantDID.id.in_(did_ids)))).scalars().all()}
    for e in exts.values():
        if e.tenant_id != src.id:
            conflicts.append(f"Le poste {e.extension} n'est pas dans {src.account_number}.")
    for d in dids.values():
        if d.tenant_id != src.id:
            conflicts.append(f"Le numéro {d.number} n'est pas dans {src.account_number}.")
    if not exts and not dids and not any(a in ("move", "copy") for m in actions.values() for a in m.values()):
        conflicts.append("Rien n'est choisi.")

    # Numeros deja utilises dans la destination (postes, groupes, interphone, parcage)
    used = {e.extension for e in (await db.execute(select(SIPExtension).where(SIPExtension.tenant_id == dst.id))).scalars().all()}
    used |= {g.extension for g in (await db.execute(select(RingGroup).where(RingGroup.tenant_id == dst.id))).scalars().all()}
    used |= {g.extension for g in (await db.execute(select(PagingGroup).where(PagingGroup.tenant_id == dst.id))).scalars().all()}
    for lot in (await db.execute(select(ParkingLot).where(ParkingLot.tenant_id == dst.id))).scalars().all():
        used |= {lot.park_extension} | {str(n) for n in range(lot.parking_slots_start, lot.parking_slots_end + 1)}

    new_num, new_user = {}, {}
    for eid, e in sorted(exts.items(), key=lambda kv: kv[1].extension):
        num = ext_sel[eid] or e.extension
        new_num[eid], new_user[eid] = num, f"{dst.account_number}-{num}"
        if num in used:
            conflicts.append(f"Le poste {num} existe déjà dans {dst.account_number} : choisissez un autre numéro pour « {e.name} ».")
        used.add(num)
        taken = (await db.execute(select(SIPExtension.id).where(SIPExtension.username == new_user[eid], SIPExtension.id != eid))).first()
        if taken:
            conflicts.append(f"L'identifiant SIP {new_user[eid]} est déjà pris.")
        steps.append(f"Poste {e.extension} « {e.name} » → {dst.account_number} comme poste {num} (identifiant {new_user[eid]}).")

    moving_users = {e.username: new_user[eid] for eid, e in exts.items()}
    # Objets avec un choix
    loaded = {}
    for kind, model in MODELS.items():
        rows = (await db.execute(select(model).where(model.tenant_id == src.id))).scalars().all()
        loaded[kind] = rows
        for o in rows:
            act = actions[kind].get(o.id, "leave")
            if act == "copy" and kind not in COPYABLE:
                conflicts.append(f"{LABELS[kind]} « {_name(kind, o)} » ne peut pas être copié (le même compte serait enregistré deux fois) : déplacez-le ou laissez-le.")
                continue
            if act in ("move", "copy"):
                verb = "déplacé" if act == "move" else "copié"
                steps.append(f"{LABELS[kind]} « {_name(kind, o)} » {verb} vers {dst.account_number}.")
                if kind in ("ring_groups", "paging_groups"):
                    if o.extension in used:
                        conflicts.append(f"Le numéro {o.extension} du {LABELS[kind].lower()} « {o.name} » existe déjà dans {dst.account_number}.")
                    used.add(o.extension)

    # Parcage automatique : la destination a toujours sa propre zone (creee ici si elle n'en a pas)
    if not await has_parking(db, dst.id):
        clash = default_numbers() & used
        if clash:
            conflicts.append(f"{dst.account_number} n'a pas encore de zone de parcage : celle par défaut (700, 701-720) doit être créée, "
                             f"mais {', '.join(sorted(clash, key=int))} y est déjà utilisé — choisissez un autre numéro de poste.")
        else:
            steps.append(f"Zone de parcage de {dst.account_number} créée (700, places 701-720).")
    old_numbers = {e.extension for e in exts.values()}
    for lot in (await db.execute(select(ParkingLot).where(ParkingLot.tenant_id == src.id))).scalars().all():
        if lot.return_extension in old_numbers:
            warnings.append(f"Le parcage de {src.account_number} renvoie les appels oubliés au poste {lot.return_extension}, qui part : "
                            "changez son poste de retour.")

    # Trunks et routes sortantes : une route ne part pas sans son trunk, un trunk ne laisse pas ses routes derriere
    for r in loaded["outbound_routes"]:
        r_moves = actions["outbound_routes"].get(r.id) == "move"
        t_moves = actions["trunks"].get(r.trunk_id) == "move"
        if r_moves and not t_moves:
            conflicts.append(f"La route sortante « {r.name} » ne peut pas partir sans son trunk : déplacez aussi le trunk.")
        if t_moves and not r_moves:
            conflicts.append(f"Le trunk part mais la route sortante « {r.name} » qui l'utilise reste : déplacez-la aussi.")

    # Membres des groupes
    for g in loaded["ring_groups"]:
        act = actions["ring_groups"].get(g.id, "leave")
        mem = (await db.execute(select(RingGroupMember).where(RingGroupMember.ring_group_id == g.id))).scalars().all()
        going = [m for m in mem if m.extension_id in exts]
        staying = [m for m in mem if m.extension_id not in exts]
        if act == "move" and staying:
            warnings.append(f"Groupe « {g.name} » déplacé : {len(staying)} poste(s) qui restent dans {src.account_number} en seront retirés.")
        if act == "leave" and going:
            warnings.append(f"Groupe « {g.name} » laissé : {', '.join(exts[m.extension_id].extension for m in going)} en seront retirés.")
        if act == "copy":
            steps.append(f"  Copie de « {g.name} » : le nouveau garde {len(going)} poste(s), l'ancien garde {len(staying)} poste(s).")

    # Liens vers des objets qui ne suivent pas
    sched_act = actions["schedules"]
    for e in exts.values():
        if e.schedule_id and sched_act.get(e.schedule_id, "leave") == "leave":
            warnings.append(f"Poste {e.extension} : son horaire reste dans {src.account_number}, il n'en aura plus.")
    for d in dids.values():
        steps.append(f"Numéro {d.number}{' « ' + d.label + ' »' if d.label else ''} → {dst.account_number}.")
        if d.schedule_id and sched_act.get(d.schedule_id, "leave") == "leave":
            warnings.append(f"Numéro {d.number} : son horaire reste dans {src.account_number}, il n'en aura plus.")
        if d.destination_type == "extension" and d.destination and d.destination not in {new_num.get(i) for i in exts} \
                and d.destination not in {e.extension for e in exts.values()}:
            warnings.append(f"Numéro {d.number} : sa destination « {d.destination} » ne part pas — à corriger dans {dst.account_number} après.")
        if d.destination_type == "message":
            p = next((p for p in loaded["prompts"] if p.name == d.destination), None)
            if p and actions["prompts"].get(p.id, "leave") == "leave":
                warnings.append(f"Numéro {d.number} : son message « {d.destination} » ne part pas (copiez-le).")

    # 911 : chaque poste / numero garde son adresse ; l'adresse suit quand plus rien ne l'utilise dans le depart
    ext_911 = {a.extension_id: a for a in (await db.execute(select(ExtensionE911Assignment).where(ExtensionE911Assignment.extension_id.in_(exts)))).scalars().all()}
    did_911 = {a.did_id: a for a in (await db.execute(select(DID911Assignment).where(DID911Assignment.did_id.in_(dids)))).scalars().all()}
    src_addrs = {a.id: a for a in (await db.execute(select(E911Address).where(E911Address.tenant_id == src.id))).scalars().all()}
    all_exts = set((await db.execute(select(SIPExtension.id).where(SIPExtension.tenant_id == src.id))).scalars().all())
    all_dids = set((await db.execute(select(TenantDID.id).where(TenantDID.tenant_id == src.id))).scalars().all())
    source_emptied = bool(exts or dids) and all_exts <= set(exts) and all_dids <= set(dids)
    if source_emptied:
        move_addrs = set(src_addrs)
    else:
        still = {a.e911_address_id for a in (await db.execute(select(ExtensionE911Assignment).where(
            ExtensionE911Assignment.extension_id.in_(all_exts - set(exts))))).scalars().all()}
        still |= {a.e911_address_id for a in (await db.execute(select(DID911Assignment).where(
            DID911Assignment.did_id.in_(all_dids - set(dids))))).scalars().all()}
        move_addrs = {a.e911_address_id for a in (*ext_911.values(), *did_911.values())} - still
    move_addrs &= set(src_addrs)
    for eid, a in ext_911.items():
        x = src_addrs.get(a.e911_address_id) or await db.get(E911Address, a.e911_address_id)
        if x:
            steps.append(f"  Poste {new_num[eid]} : garde son adresse 911 {x.civic_number} {x.street_name}, {x.city}.")
    for did_id, a in did_911.items():
        x = src_addrs.get(a.e911_address_id) or await db.get(E911Address, a.e911_address_id)
        if x:
            steps.append(f"  Numéro {dids[did_id].number} : garde son adresse 911 {x.civic_number} {x.street_name}, {x.city}.")
    for aid in move_addrs:
        x = src_addrs[aid]
        steps.append(f"Adresse 911 « {x.label} » ({x.civic_number} {x.street_name}, {x.city}) → {dst.account_number}.")
    if source_emptied:
        steps.append(f"{src.account_number} n'a plus de poste ni de numéro : il sera désactivé (pas supprimé).")

    # Messages vocaux, telephones, sortie vers l'exterieur, historique
    vm = dict((await db.execute(select(VoicemailBox.extension_id, func.count(VoicemailMessage.id))
                                .join(VoicemailMessage, VoicemailMessage.mailbox_id == VoicemailBox.id)
                                .where(VoicemailBox.extension_id.in_(exts)).group_by(VoicemailBox.extension_id))).all())
    for eid, n in vm.items():
        if n:
            warnings.append(f"Poste {exts[eid].extension} : {n} message(s) vocal(aux) déjà reçu(s) restent dans l'ancienne boîte — écoutez-les avant.")
    phones = (await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.extension_id.in_(exts)))).scalars().all()
    if phones:
        steps.append(f"{len(phones)} téléphone(s) reprovisionné(s) avec le nouvel identifiant (ils redémarrent).")
    elif exts:
        warnings.append("Aucun téléphone provisionné par le serveur pour ces postes : configurez le nouvel identifiant à la main.")
    has_route = (await db.execute(select(OutboundRoute.id).where(OutboundRoute.tenant_id == dst.id).limit(1))).first() \
        or any(actions["outbound_routes"].get(r.id) == "move" for r in loaded["outbound_routes"])
    if exts and not has_route:
        warnings.append(f"{dst.account_number} n'a aucune route sortante : ses postes ne pourront pas appeler à l'extérieur (ajoutez un trunk et une route).")
    if exts or dids:
        steps.append("Historique d'appels de ces postes et numéros : gardé dans l'ancien tenant, marqué « migré ».")
        steps.append("Facturation : retrait dans l'ancienne compagnie, ajout dans la nouvelle (prorata).")

    ctx = {"src": src, "dst": dst, "exts": exts, "dids": dids, "new_num": new_num, "new_user": new_user, "actions": actions,
           "loaded": loaded, "ext_911": ext_911, "did_911": did_911, "move_addrs": move_addrs, "source_emptied": source_emptied,
           "phones": phones, "moving_users": moving_users}
    return {"steps": steps, "conflicts": conflicts, "warnings": warnings, "ctx": ctx}


async def preview(db: AsyncSession, sel: dict) -> dict:
    p = await _plan(db, sel)
    return {"ok": not p["conflicts"], "steps": p["steps"], "conflicts": p["conflicts"], "warnings": p["warnings"]}


# ── Execution ────────────────────────────────────────────────────────────────

def backup_database(label: str) -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(settings.DATABASE_URL.replace("+asyncpg", ""))
    path = BACKUP_DIR / f"migration_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"
    subprocess.run(["pg_dump", "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432), "-U", parsed.username or "",
                    "-d", (parsed.path or "/").lstrip("/"), "-Fc", "-f", str(path)],
                   check=True, env={"PGPASSWORD": parsed.password or ""})
    return str(path)


def _clone(model, o, **over):
    cols = {c.key: getattr(o, c.key) for c in model.__table__.columns}
    cols.update(id=uuid.uuid4(), **over)
    return model(**cols)


def _copy_file(folder: Path, filename: str) -> str:
    src = folder / filename
    new = f"{uuid.uuid4()}{Path(filename).suffix}"
    if src.exists():
        shutil.copy2(src, folder / new)
    return new


async def execute(db: AsyncSession, sel: dict) -> dict:
    if not sel.get("dest_tenant_id"):
        return {"ok": False, "conflicts": ["Le tenant d'arrivée doit être créé avant la migration."], "warnings": [], "steps": []}
    p = await _plan(db, sel)
    if p["conflicts"]:
        return {"ok": False, "conflicts": p["conflicts"], "warnings": p["warnings"], "steps": p["steps"]}
    c = p["ctx"]
    src, dst, exts, dids, actions, loaded = c["src"], c["dst"], c["exts"], c["dids"], c["actions"], c["loaded"]
    backup = backup_database(f"{src.account_number}_to_{dst.account_number}")
    now = datetime.now(timezone.utc)
    maps = {k: {} for k in MODELS}          # ancien id -> nouvel id (meme id si deplace, None si laisse)
    old_users = {eid: e.username for eid, e in exts.items()}
    old_nums = {eid: e.extension for eid, e in exts.items()}

    def remap(kind, old_id):
        if not old_id:
            return None
        a = actions[kind].get(old_id, "leave")
        return maps[kind].get(old_id) if a in ("move", "copy") else None

    # 1. Objets sans dependance : horaires, messages, musique, trunks, feries
    for s in loaded["schedules"]:
        a = actions["schedules"].get(s.id, "leave")
        if a == "move":
            s.tenant_id = dst.id; maps["schedules"][s.id] = s.id
        elif a == "copy":
            n = _clone(Schedule, s, tenant_id=dst.id); db.add(n); await db.flush(); maps["schedules"][s.id] = n.id
            for r in (await db.execute(select(ScheduleRule).where(ScheduleRule.schedule_id == s.id))).scalars().all():
                db.add(_clone(ScheduleRule, r, schedule_id=n.id))
    for pr in loaded["prompts"]:
        a = actions["prompts"].get(pr.id, "leave")
        if a == "move":
            pr.tenant_id = dst.id; maps["prompts"][pr.id] = pr.id
        elif a == "copy":
            n = _clone(AudioPrompt, pr, tenant_id=dst.id, filename=_copy_file(PROMPT_DIR, pr.filename)); db.add(n); await db.flush()
            maps["prompts"][pr.id] = n.id
    for sm in loaded["moh"]:
        a = actions["moh"].get(sm.id, "leave")
        if a not in ("move", "copy"):
            continue
        f = await db.get(MohFile, sm.moh_file_id)
        file_id = sm.moh_file_id
        if f and f.tenant_id == src.id:          # fichier propre au tenant : suit ou est copie
            if a == "move":
                f.tenant_id = dst.id
            else:
                nf = _clone(MohFile, f, tenant_id=dst.id, filename=_copy_file(MOH_DIR, f.filename)); db.add(nf); await db.flush(); file_id = nf.id
        if a == "move":
            sm.tenant_id, sm.moh_file_id = dst.id, file_id
        else:
            db.add(_clone(TenantMohSelection, sm, tenant_id=dst.id, moh_file_id=file_id))
    for tr in loaded["trunks"]:
        if actions["trunks"].get(tr.id) == "move":
            tr.tenant_id = dst.id; maps["trunks"][tr.id] = tr.id
    for r in loaded["outbound_routes"]:
        if actions["outbound_routes"].get(r.id) == "move":
            r.tenant_id = dst.id
    for h in loaded["holidays"]:
        a = actions["holidays"].get(h.id, "leave")
        if a == "move":
            h.tenant_id = dst.id
        elif a == "copy":
            db.add(_clone(Holiday, h, tenant_id=dst.id))
    await db.flush()

    # 2. Postes
    for eid, e in exts.items():
        e.tenant_id, e.extension, e.username = dst.id, c["new_num"][eid], c["new_user"][eid]
        e.schedule_id = remap("schedules", e.schedule_id)
        e.preferred_trunk_id = remap("trunks", e.preferred_trunk_id)
        await db.execute(update(VoicemailBox).where(VoicemailBox.extension_id == eid).values(tenant_id=dst.id, mailbox=e.extension))
        await db.execute(update(ProvisionedPhone).where(ProvisionedPhone.extension_id == eid).values(tenant_id=dst.id))
        await db.execute(update(ExtensionE911Assignment).where(ExtensionE911Assignment.extension_id == eid).values(tenant_id=dst.id))
    await db.flush()

    # 3. Groupes, files, interphone, interception, parcage, IVR
    moving_ids = set(exts)
    users = c["moving_users"]

    def keep_csv(csv: str | None, keep_moving: bool) -> str:
        out = []
        for u in (csv or "").split(","):
            u = u.strip()
            if not u:
                continue
            if u in users:
                if keep_moving:
                    out.append(users[u])
            elif not keep_moving:
                out.append(u)
        return ",".join(out)

    for g in loaded["ring_groups"]:
        a = actions["ring_groups"].get(g.id, "leave")
        mem = (await db.execute(select(RingGroupMember).where(RingGroupMember.ring_group_id == g.id))).scalars().all()
        if a == "move":
            g.tenant_id, g.schedule_id = dst.id, remap("schedules", g.schedule_id)
            g.members = keep_csv(g.members, keep_moving=True)
            for m in mem:
                if m.extension_id not in moving_ids:
                    await db.delete(m)
        elif a == "copy":
            n = _clone(RingGroup, g, tenant_id=dst.id, members=keep_csv(g.members, True), schedule_id=remap("schedules", g.schedule_id))
            db.add(n); await db.flush()
            for m in mem:
                if m.extension_id in moving_ids:
                    db.add(_clone(RingGroupMember, m, ring_group_id=n.id))
                    await db.delete(m)
            for st in (await db.execute(select(RingGroupFailoverStep).where(RingGroupFailoverStep.ring_group_id == g.id))).scalars().all():
                db.add(_clone(RingGroupFailoverStep, st, ring_group_id=n.id))
            g.members = keep_csv(g.members, keep_moving=False)
        else:
            g.members = keep_csv(g.members, keep_moving=False)
            for m in mem:
                if m.extension_id in moving_ids:
                    await db.delete(m)
    for g in loaded["paging_groups"]:
        a = actions["paging_groups"].get(g.id, "leave")
        mem = (await db.execute(select(PagingGroupMember).where(PagingGroupMember.paging_group_id == g.id))).scalars().all()
        if a == "move":
            g.tenant_id = dst.id
            for m in mem:
                if m.extension_id not in moving_ids:
                    await db.delete(m)
        elif a == "copy":
            n = _clone(PagingGroup, g, tenant_id=dst.id); db.add(n); await db.flush()
            for m in mem:
                if m.extension_id in moving_ids:
                    db.add(_clone(PagingGroupMember, m, paging_group_id=n.id)); await db.delete(m)
        else:
            for m in mem:
                if m.extension_id in moving_ids:
                    await db.delete(m)
    for q in loaded["queues"]:
        a = actions["queues"].get(q.id, "leave")
        mem = (await db.execute(select(QueueMember).where(QueueMember.queue_id == q.id))).scalars().all()
        if a == "move":
            q.tenant_id = dst.id
            for m in mem:
                if m.extension_username in users:
                    m.extension_username = users[m.extension_username]
                else:
                    await db.delete(m)
        elif a == "copy":
            n = _clone(Queue, q, tenant_id=dst.id, queue_name=f"{q.queue_name}-{dst.account_number}"); db.add(n); await db.flush()
            for m in mem:
                if m.extension_username in users:
                    db.add(_clone(QueueMember, m, queue_id=n.id, extension_username=users[m.extension_username])); await db.delete(m)
        else:
            for m in mem:
                if m.extension_username in users:
                    await db.delete(m)
    for g in loaded["pickup_groups"]:
        a = actions["pickup_groups"].get(g.id, "leave")
        if a == "move":
            g.tenant_id = dst.id
        elif a == "copy":
            db.add(_clone(PickupGroup, g, tenant_id=dst.id))
        else:
            for e in exts.values():
                if e.pickup_group == g.name:
                    e.pickup_group = None
    await ensure_default_parking(db, dst.id)
    for ivr in loaded["ivrs"]:
        a = actions["ivrs"].get(ivr.id, "leave")
        if a == "move":
            ivr.tenant_id, ivr.greeting_prompt_id = dst.id, remap("prompts", ivr.greeting_prompt_id)
        elif a == "copy":
            n = _clone(IVR, ivr, tenant_id=dst.id, greeting_prompt_id=remap("prompts", ivr.greeting_prompt_id)); db.add(n); await db.flush()
            for o in (await db.execute(select(IVROption).where(IVROption.ivr_id == ivr.id))).scalars().all():
                db.add(_clone(IVROption, o, ivr_id=n.id))
    await db.flush()

    # 4. Numeros (et leurs routes entrantes, leur 911)
    for did_id, d in dids.items():
        d.tenant_id, d.schedule_id = dst.id, remap("schedules", d.schedule_id)
        if d.destination_type == "extension":
            for eid, num in old_nums.items():
                if d.destination == num:
                    d.destination = c["new_num"][eid]
        await db.execute(update(InboundRoute).where(InboundRoute.did_id == did_id).values(tenant_id=dst.id))
        await db.execute(update(DID911Assignment).where(DID911Assignment.did_id == did_id).values(tenant_id=dst.id))
    for aid in c["move_addrs"]:
        await db.execute(update(E911Address).where(E911Address.id == aid).values(tenant_id=dst.id))
    if c["source_emptied"]:
        src.is_active = False

    # 5. Historique d'appels : garde, marque
    marks = []
    for eid in exts:
        u, n = old_users[eid], old_nums[eid]
        marks.append(or_(CDR.src == n, CDR.dst == n, CDR.src == u, CDR.dst == u,
                         CDR.channel.like(f"%{u}%"), CDR.dstchannel.like(f"%{u}%")))
    for d in dids.values():
        tail = d.number[-10:]
        marks.append(or_(CDR.src.like(f"%{tail}"), CDR.dst.like(f"%{tail}")))
    cdr_marked = 0
    if marks:
        r = await db.execute(update(CDR).where(CDR.tenant_id == src.id, CDR.migrated_at.is_(None), or_(*marks))
                             .values(migrated_at=now, migrated_to_tenant_id=dst.id))
        cdr_marked = r.rowcount or 0

    await db.commit()
    return {"ok": True, "backup": backup, "steps": p["steps"], "warnings": p["warnings"], "cdr_marked": cdr_marked,
            "moved_extensions": [{"id": str(eid), "old_username": old_users[eid], "username": c["new_user"][eid],
                                  "old_number": old_nums[eid], "number": c["new_num"][eid], "name": exts[eid].name,
                                  "erpcrm_contact_id": str(exts[eid].erpcrm_contact_id) if exts[eid].erpcrm_contact_id else None}
                                 for eid in exts],
            "moved_dids": [{"id": str(i), "number": d.number, "erpcrm_did_id": str(d.erpcrm_did_id) if d.erpcrm_did_id else None}
                           for i, d in dids.items()],
            "moved_addresses": [str(a) for a in c["move_addrs"]], "source_emptied": c["source_emptied"],
            "source": {"id": str(src.id), "account_number": src.account_number},
            "dest": {"id": str(dst.id), "account_number": dst.account_number},
            "moh_changed": any(a in ("move", "copy") for a in actions["moh"].values())}
