"""
mod_xml_curl — FreeSWITCH dynamic XML configuration endpoint.

FreeSWITCH calls POST /api/v1/xml_curl (form-encoded) for every config lookup.
We return XML; FreeSWITCH uses it as if it were a local config file.

Sections handled:
  directory     → SIP user auth + variables (called on every REGISTER / INVITE)
  dialplan      → call routing (called on every call)
  configuration → ivr.conf menus (called when ivr application runs)

Multi-tenant mapping:
  Tenant.account_number  = FreeSWITCH domain  (e.g.  "ACME")
  SIPExtension.username  = SIP user id         (e.g.  "ACME-201")
  Internal dialplan ctx  = "internal-ACME"
  Inbound trunk context  = "public"

FreeSWITCH sofia profile must have:
  <param name="context" value="public"/>          ← for inbound trunk calls
  <param name="xml-curl-use-dynamic-hash" value="false"/>

event_socket.conf.xml xml-curl pointing to:
  http://127.0.0.1:8020/api/v1/xml_curl
"""
import html
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.crypto import decrypt
from app.core.nanp import CANADIAN_AREA_CODES
from app.models.tenant import Tenant
from app.models.sip import SIPExtension, TenantDID
from app.models.dialplan import InboundRoute, OutboundRoute
from app.models.ivr import IVR, IVROption, RingGroup
from app.models.cdr import CDR

router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────

XML_HDR = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'

NOT_FOUND = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found"/>
  </section>
</document>"""


def _resp(xml: str) -> Response:
    return Response(content=xml, media_type="text/xml")


def xe(v) -> str:
    """Escape value for XML attributes/text."""
    return html.escape(str(v or ""), quote=True)


def _context_name(account_number: str) -> str:
    return f"internal-{account_number}"


def _bridge(username: str, domain: str) -> str:
    # "user/" declenche la resolution via le dial-string du domaine (voir directory XML,
    # param dial-string -> sofia_contact) plutot qu'un "sofia/internal/user@domain" litteral,
    # qui fait tenter a FreeSWITCH une resolution DNS de "domain" (notre tenant, pas un vrai
    # nom DNS) -> "503 DNS Error" systematique. Confirme par test reel le 2026-07-18.
    return f"user/{xe(username)}@{xe(domain)}"


# Nommage convenu avec l'utilisateur (TASK-023.4, 2026-07-24) : appelant-appele-date-heure.
_RECORDINGS_DIR = "/usr/local/freeswitch/recordings"


def _record_action(enabled: bool) -> str:
    if not enabled:
        return ""
    path = f"{_RECORDINGS_DIR}/${{caller_id_number}}-${{destination_number}}-${{strftime(%Y%m%d-%H%M%S)}}.wav"
    return f'\n          <action application="record_session" data="{path}"/>'


# ── Main router ────────────────────────────────────────────────────────────────

@router.post("")
async def xml_curl(request: Request, db: AsyncSession = Depends(get_db)):
    """FreeSWITCH mod_xml_curl — main entry point."""
    form = await request.form()
    section = form.get("section", "")

    if section == "directory":
        return await _handle_directory(form, db)
    if section == "dialplan":
        return await _handle_dialplan(form, db)
    if section == "configuration":
        return await _handle_configuration(form, db)
    return _resp(NOT_FOUND)


# ── DIRECTORY ─────────────────────────────────────────────────────────────────

async def _handle_directory(form, db: AsyncSession) -> Response:
    """
    Return SIP user credentials + variables for a given domain/user.
    Called by FreeSWITCH on every REGISTER and authenticated INVITE.

    FreeSWITCH form fields:
      key_value  = domain (= account_number)
      user       = SIP username (= SIPExtension.username)
    """
    domain = form.get("key_value", "") or form.get("domain", "")
    # FreeSWITCH envoie parfois le username d'auth avec un "@" (et parfois "@domaine") en
    # suffixe (ex: "t1001-100@") — on ne garde que la partie avant le "@".
    username = form.get("user", "").split("@")[0]

    # Lookup tenant by account_number (= domain), si le domaine envoye en matche un.
    tenant = None
    if domain:
        result = await db.execute(
            select(Tenant).where(Tenant.account_number == domain, Tenant.is_active == True)
        )
        tenant = result.scalar_one_or_none()

    # Lookup specific user if provided
    if username:
        ext_query = select(SIPExtension).where(
            SIPExtension.username == username,
            SIPExtension.is_active == True,
        )
        if tenant:
            ext_query = ext_query.where(SIPExtension.tenant_id == tenant.id)
        result = await db.execute(ext_query)
        ext = result.scalar_one_or_none()
        if not ext:
            return _resp(NOT_FOUND)
        if not tenant:
            # Connexion "conventionnelle" : le client a mis l'adresse du serveur (ou
            # n'importe quoi d'autre) comme domaine, pas le tenant -- le username SIP
            # est deja globalement unique (contrainte a la creation), donc on retrouve
            # le tenant via son VRAI lien (tenant_id, cle etrangere), pas via le domaine
            # envoye. Demande explicite de l'utilisateur (2026-07-24) : le tenant est
            # une "boite" liee au poste par relation, jamais par convention de nommage.
            tenant = await db.get(Tenant, ext.tenant_id)
            if not tenant or not tenant.is_active:
                return _resp(NOT_FOUND)
        # Force le transport configure pour ce poste — uniquement verifie au REGISTER
        # (sip_via_protocol absent lors des lookups internes type "user/xxx@domain" pour
        # le bridge d'appel, qu'on ne veut pas bloquer).
        if form.get("sip_auth_method") == "REGISTER":
            via_protocol = (form.get("sip_via_protocol") or "").lower()
            if via_protocol and via_protocol != ext.transport:
                return _resp(NOT_FOUND)
        return _resp(_directory_single_user(tenant, ext, advertised_domain=domain))

    if not tenant:
        return _resp(NOT_FOUND)

    # No specific user → return full domain with all extensions
    result = await db.execute(
        select(SIPExtension).where(
            SIPExtension.tenant_id == tenant.id,
            SIPExtension.is_active == True,
        )
    )
    extensions = result.scalars().all()
    return _resp(_directory_full_domain(tenant, extensions))


_CODEC_MAP = {"ulaw": "PCMU", "alaw": "PCMA", "g722": "G722", "g729": "G729"}
# ⚠️ toll_allow reflete call_permission mais n'est PAS applique par le dialplan --
# OutboundRoute (xml_curl.py _handle_dialplan) n'a aucune verification de palier
# d'appel. Decoratif tant que ce n'est pas cable explicitement (TASK-S018.3).
_TOLL_ALLOW_MAP = {
    "local": "local",
    "national": "domestic,local",
    "international": "domestic,international,local",
}


def _user_xml(ext: "SIPExtension", tenant: "Tenant") -> str:
    # --- TASK-018.6 : caller ID separe interne/externe. `caller_id_name/number`
    # (generique) reste le fallback intermediaire pour compat ascendante -- les
    # extensions crees avant cette tache continuent de fonctionner identiquement
    # tant que les nouveaux champs specifiques ne sont pas remplis.
    int_name = xe(ext.caller_id_internal_name or ext.caller_id_name or ext.name)
    int_num = xe(ext.caller_id_internal_number or ext.caller_id_number or ext.extension)
    ext_name = xe(ext.caller_id_external_name or ext.caller_id_name or tenant.default_caller_id_name or ext.name)
    ext_num = xe(ext.caller_id_external_number or ext.caller_id_number or tenant.default_caller_id_number or ext.extension)
    domain = tenant.account_number
    context = xe(_context_name(domain))
    vm = "true" if ext.voicemail_enabled else "false"
    codec_var = ""
    fs_codecs = [_CODEC_MAP[c] for c in (ext.codec_list or "").split(",") if c in _CODEC_MAP]
    if fs_codecs:
        codec_var = f'\n                <variable name="absolute_codec_string" value="{",".join(fs_codecs)}"/>'
    toll_allow = _TOLL_ALLOW_MAP.get(ext.call_permission, _TOLL_ALLOW_MAP["international"])
    # Masquer le caller ID -- applique seulement au sortant externe (outbound_*),
    # jamais au interne (effective_*) : un collegue doit toujours voir qui appelle.
    privacy_var = ""
    if ext.hide_caller_id:
        privacy_var = '\n                <variable name="origination_privacy" value="hide_name:hide_number:screen"/>'
    return f"""            <user id="{xe(ext.username)}">
              <params>
                <param name="password" value="{xe(decrypt(ext.password))}"/>
              </params>
              <variables>
                <variable name="user_context" value="{context}"/>
                <variable name="effective_caller_id_name" value="{int_name}"/>
                <variable name="effective_caller_id_number" value="{int_num}"/>
                <variable name="outbound_caller_id_name" value="{ext_name}"/>
                <variable name="outbound_caller_id_number" value="{ext_num}"/>{privacy_var}
                <variable name="voicemail_enabled" value="{vm}"/>
                <variable name="accountcode" value="{xe(ext.username)}"/>
                <variable name="toll_allow" value="{toll_allow}"/>{codec_var}
                <variable name="rtp_secure_media" value="mandatory"/>
              </variables>
            </user>"""


def _directory_single_user(tenant: "Tenant", ext: "SIPExtension", advertised_domain: str | None = None) -> str:
    # FreeSWITCH (switch_xml_locate_domain, verifie dans le code source) exige que le
    # <domain name="..."> retourne corresponde EXACTEMENT au domaine demande dans la
    # requete originale, peu importe le vrai tenant trouve derriere. Pour une connexion
    # "conventionnelle" (le client met l'IP du serveur comme domaine, pas le tenant),
    # `advertised_domain` = ce que le client a envoye ; le contexte/routage interne
    # (user_context via _user_xml) continue d'utiliser le VRAI domaine du tenant.
    domain = xe(advertised_domain or tenant.account_number)
    dial_str = (
        "{presence_id=${dialed_user}@${dialed_domain}}"
        "${sofia_contact(*/${dialed_user}@${dialed_domain})}"
    )
    return f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="{domain}">
      <params>
        <param name="dial-string" value="{xe(dial_str)}"/>
      </params>
      <groups>
        <group name="default">
          <users>
{_user_xml(ext, tenant)}
          </users>
        </group>
      </groups>
    </domain>
  </section>
</document>"""


def _directory_full_domain(tenant: "Tenant", extensions: list) -> str:
    domain = xe(tenant.account_number)
    dial_str = (
        "{presence_id=${dialed_user}@${dialed_domain}}"
        "${sofia_contact(*/${dialed_user}@${dialed_domain})}"
    )
    users_xml = "\n".join(_user_xml(ext, tenant) for ext in extensions)
    return f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="{domain}">
      <params>
        <param name="dial-string" value="{xe(dial_str)}"/>
      </params>
      <groups>
        <group name="default">
          <users>
{users_xml}
          </users>
        </group>
      </groups>
    </domain>
  </section>
</document>"""


# ── DIALPLAN ──────────────────────────────────────────────────────────────────

async def _handle_dialplan(form, db: AsyncSession) -> Response:
    """
    Return routing rules for a given context.

    Un vrai lookup dialplan FreeSWITCH (mod_dialplan_xml) n'envoie PAS les champs
    simples "context"/"destination_number" — il envoie un evenement complet avec
    "Caller-Context", "Caller-Destination-Number", "variable_sip_from_host", etc.
    (confirme par capture reelle le 2026-07-18 — le code precedent lisait des champs
    qui n'existaient jamais dans une vraie requete).

    internal-{account}  → contexte historique explicite (jamais emis en pratique par
                           FreeSWITCH — le profil sofia "internal" a un seul context
                           statique, pas un par tenant — garde pour compatibilite)
    public              → inbound DID routing (from trunks)
    sipv-internal       → contexte reel du profil sofia "internal" (voir internal.xml) ;
                           le tenant est determine ICI, au debut du routage, via le
                           domaine d'origine de l'appelant (variable_sip_from_host) —
                           pas via une variable per-user qui ne se propage pas de facon fiable
    """
    context = form.get("Caller-Context") or form.get("context", "")
    destination = form.get("Caller-Destination-Number") or form.get("destination_number", "")

    if context.startswith("internal-"):
        account = context[len("internal-"):]
        return await _dialplan_internal(account, destination, db, requested_context=context)

    if context == "public":
        return await _dialplan_public(destination, db)

    if context == "sipv-internal":
        account = form.get("variable_sip_from_host", "")
        caller_username = (form.get("variable_sip_from_user") or "").split("@")[0]
        if account or caller_username:
            return await _dialplan_internal(account, destination, db, requested_context=context, caller_username=caller_username)

    return _resp(NOT_FOUND)


async def _dialplan_internal(account: str, destination: str, db: AsyncSession, requested_context: str | None = None, caller_username: str | None = None) -> Response:
    """
    Dialplan for internal tenant context.
    Handles:
      - Extension-to-extension calls
      - Ring group calls
      - Voicemail access (*97, *98)
      - Outbound calls via configured routes

    requested_context : le nom de contexte EXACT que FreeSWITCH a demande (Caller-Context).
    Le XML <context name="..."> retourne doit correspondre EXACTEMENT a ce qui a ete
    demande, sinon FreeSWITCH rejette la reponse comme "not found" meme si elle contient
    un dialplan valide sous un autre nom.
    """
    tenant = None
    if account:
        result = await db.execute(
            select(Tenant).where(Tenant.account_number == account, Tenant.is_active == True)
        )
        tenant = result.scalar_one_or_none()

    # Poste appelant -- necessaire pour le tenant en connexion "conventionnelle" (voir
    # plus bas) ET pour savoir si CET appel doit etre enregistre automatiquement
    # (record_internal_outgoing / record_external_outgoing, TASK-023.4).
    caller_ext = None
    if caller_username:
        result = await db.execute(
            select(SIPExtension).where(
                SIPExtension.username == caller_username,
                SIPExtension.is_active == True,
            )
        )
        caller_ext = result.scalar_one_or_none()

    if not tenant and caller_ext:
        # Connexion "conventionnelle" (domaine = adresse du serveur, pas le tenant) --
        # meme principe que _handle_directory : retrouver le tenant via le vrai lien
        # (SIPExtension.tenant_id) du poste appelant, pas via le domaine envoye.
        tenant = await db.get(Tenant, caller_ext.tenant_id)
        if tenant and not tenant.is_active:
            tenant = None

    if not tenant:
        return _resp(NOT_FOUND)

    # All active extensions for this tenant
    result = await db.execute(
        select(SIPExtension).where(
            SIPExtension.tenant_id == tenant.id,
            SIPExtension.is_active == True,
        )
    )
    extensions = result.scalars().all()

    # Ring groups (ring_members eager-charge -- TASK-023.9)
    result = await db.execute(
        select(RingGroup).options(selectinload(RingGroup.ring_members)).where(
            RingGroup.tenant_id == tenant.id,
            RingGroup.is_active == True,
        )
    )
    ring_groups = result.scalars().all()

    # Outbound routes (ordered by priority)
    result = await db.execute(
        select(OutboundRoute).where(
            OutboundRoute.tenant_id == tenant.id,
            OutboundRoute.is_active == True,
        ).order_by(OutboundRoute.priority)
    )
    out_routes = result.scalars().all()

    ctx = xe(requested_context or f"internal-{account}")
    domain = xe(account)
    ext_entries = _ext_dialplan_entries(extensions, domain, account, ctx, caller_ext)
    rg_entries = await _ringgroup_dialplan_entries(ring_groups, domain, extensions, db, ctx)
    gate_entries = await _call_permission_gate_entries(caller_ext, tenant, out_routes, account, db)
    outbound_entries = _outbound_dialplan_entries(out_routes, account, caller_ext)

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="{ctx}">

      <!-- Voicemail check: *97 -->
      <extension name="voicemail_check">
        <condition field="destination_number" expression="^\\*97$">
          <action application="answer"/>
          <action application="voicemail" data="check default ${{domain_name}} ${{caller_id_number}}"/>
        </condition>
      </extension>

      <!-- Voicemail direct: *98+extension -->
      <extension name="voicemail_direct">
        <condition field="destination_number" expression="^\\*98([0-9]+)$">
          <action application="answer"/>
          <action application="voicemail" data="default ${{domain_name}} $1"/>
        </condition>
      </extension>

{ext_entries}
{rg_entries}
{gate_entries}
{outbound_entries}

      <!-- Catch-all: busy -->
      <extension name="catchall">
        <condition field="destination_number" expression="^(.*)$">
          <action application="respond" data="486 Busy Here"/>
        </condition>
      </extension>

    </context>
  </section>
</document>"""
    return _resp(xml)


# Types de destination geres pour les renvois (TASK-023.6). "external" (aucun trunk
# reellement provisionne/actif dans ce projet pour l'instant -- appels externes
# reportes, voir TASKSIPV "Points critiques") et queue/ivr/recording (pas de
# convention de resolution etablie) sont acceptes en stockage (champ libre, voir
# extensions.py) mais PAS encore resolus ici -- si un de ces types est choisi, le
# renvoi n'est pas applique et le poste sonne normalement (repli sur le comportement
# existant plutot qu'un bridge devine/casse).
def _forward_action_xml(dest_type: str, dest_value: str | None, ext: "SIPExtension", domain: str, account: str, ctx: str) -> str | None:
    """Retourne le fragment <action .../> qui redirige l'appel vers la destination
    de renvoi, ou None si le type n'est pas encore supporte / valeur manquante."""
    value = (dest_value or "").strip()
    if dest_type == "voicemail":
        target = value or ext.username
        return f'<action application="voicemail" data="default ${{domain_name}} {xe(target)}"/>'
    if dest_type == "extension" and value:
        return f'<action application="bridge" data="{_bridge(f"{account}-{value}", domain)}"/>'
    if dest_type == "ring_group" and value:
        return f'<action application="execute_extension" data="{xe(f"rg_{value}")} XML {ctx}"/>'
    return None


def _ext_dialplan_entries(extensions: list, domain: str, account: str, ctx: str, caller_ext: "SIPExtension | None" = None) -> str:
    # Enregistrement automatique "interne" (TASK-023.4) : declenche si le poste
    # APPELANT a active le sortant, OU si le poste APPELE (destinataire de cette
    # entree) a active l'entrant -- soit l'un soit l'autre suffit.
    caller_wants_record = bool(caller_ext and caller_ext.record_internal_outgoing)
    entries = []
    for ext in extensions:
        name = xe(f"ext_{ext.extension}")
        num = xe(ext.extension)
        record_action = _record_action(caller_wants_record or ext.record_internal_incoming)

        # --- TASK-023.6 : renvoi immediat / DND -- le poste ne sonne PAS du tout,
        # redirige tout de suite. Ne change RIEN pour un poste sans renvoi/DND actif
        # (comportement identique a avant cette tache -- verifie explicitement pour
        # ne pas casser les postes existants qui n'ont ni l'un ni l'autre configure).
        diversion = None
        if ext.forward_immediate_enabled:
            diversion = _forward_action_xml(ext.forward_immediate_destination_type, ext.forward_immediate_destination, ext, domain, account, ctx)
        elif ext.dnd_enabled:
            # DND sans renvoi immediat configure -- va a la boite vocale si activee, sinon occupe.
            diversion = '<action application="voicemail" data="default ${domain_name} ' + xe(ext.username) + '"/>' if ext.voicemail_enabled else '<action application="respond" data="486 Busy Here"/>'

        if diversion:
            entries.append(f"""      <!-- Extension {ext.extension}: {xe(ext.name)} (renvoi immediat/DND) -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">{record_action}
          {diversion}
        </condition>
      </extension>""")
            continue

        bridge = _bridge(ext.username, domain)
        vm_action = ""
        if ext.voicemail_enabled:
            vm_action = f'\n          <action application="voicemail" data="default ${{domain_name}} {xe(ext.username)}"/>'
        entries.append(f"""      <!-- Extension {ext.extension}: {xe(ext.name)} -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="ringback=${{us-ring}}"/>{record_action}
          <action application="bridge" data="{bridge}"/>{vm_action}
        </condition>
      </extension>""")
    return "\n\n".join(entries)


async def _is_schedule_open(schedule_id, db: AsyncSession) -> bool:
    """
    Meme logique que schedules.py::check_is_open() (pas refactore en commun pour ne
    pas toucher un endpoint deja en prod pour cette tache -- petite duplication
    assumee, voir TASK-023.9). Retourne True si pas de schedule (aucune restriction).
    """
    import zoneinfo
    from app.models.schedule import Schedule, ScheduleRule, Holiday

    sched = await db.get(Schedule, schedule_id)
    if not sched or not sched.is_active:
        return False if sched else True
    try:
        tz = zoneinfo.ZoneInfo(sched.timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/Montreal")
    now_local = datetime.now(tz)
    today = now_local.date()
    now_time = now_local.time().replace(second=0, microsecond=0)
    weekday = now_local.weekday()

    holidays = await db.execute(select(Holiday).where(Holiday.tenant_id == sched.tenant_id))
    for h in holidays.scalars().all():
        match = (h.date.month == today.month and h.date.day == today.day) if h.recurring else (h.date == today)
        if match:
            return False

    rules = await db.execute(select(ScheduleRule).where(ScheduleRule.schedule_id == schedule_id))
    for r in rules.scalars().all():
        days = [int(d) for d in r.days_of_week.split(",") if d]
        if weekday in days and r.open_time <= now_time < r.close_time:
            return True
    return False


async def _ringgroup_dialplan_entries(ring_groups: list, domain: str, extensions: list, db: AsyncSession, ctx: str) -> str:
    ext_by_id = {e.id: e for e in extensions}
    entries = []
    for rg in ring_groups:
        name = xe(f"rg_{rg.extension}")
        num = xe(rg.extension)

        # --- TASK-023.9 : horaire d'appartenance -- groupe ferme, ne sonne personne ---
        if rg.schedule_id and not await _is_schedule_open(rg.schedule_id, db):
            fallback = rg.no_answer_destination
            if fallback:
                entries.append(f"""      <!-- Ring group {rg.extension}: {xe(rg.name)} (ferme -- horaire) -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="transfer" data="{xe(fallback)} XML {ctx}"/>
        </condition>
      </extension>""")
            continue

        # Priorite (RingGroupMember) sur la table structuree si elle a des membres,
        # sinon repli sur l'ancien CSV `members` (compat -- CRUD table pas encore fait,
        # voir TASK-023.9 reste a faire) -- comportement IDENTIQUE a avant pour tout
        # groupe qui n'a pas encore ete migre vers la nouvelle table.
        active_members = [rgm for rgm in (rg.ring_members or []) if not rgm.temporarily_excluded]
        if active_members:
            if rg.ring_strategy == "hunt":
                active_members.sort(key=lambda m: (m.ring_order, m.priority))
            else:
                active_members.sort(key=lambda m: m.priority)
            usernames = [ext_by_id[m.extension_id].username for m in active_members if m.extension_id in ext_by_id]
        else:
            usernames = [m.strip() for m in (rg.members or "").split(",") if m.strip()]

        if not usernames:
            continue

        confirm_prefix = ""
        if rg.confirm_before_answer:
            confirm_prefix = "{group_confirm_key=1,group_confirm_file=ivr/ivr-call_being_transferred.wav}"

        if rg.ring_strategy == "simultaneous":
            # All at once: separate with :_:
            bridge_str = ":_:".join(f"{confirm_prefix}{_bridge(m, domain)}" for m in usernames)
        else:
            # Hunt: one at a time
            bridge_str = ":".join(f"{confirm_prefix}{_bridge(m, domain)}" for m in usernames)
        timeout = xe(str(rg.ring_time))
        entries.append(f"""      <!-- Ring group {rg.extension}: {xe(rg.name)} -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="call_timeout={timeout}"/>
          <action application="set" data="ringback=${{us-ring}}"/>
          <action application="bridge" data="{xe(bridge_str)}"/>
        </condition>
      </extension>""")
    return "\n\n".join(entries)


def _resolve_call_permission(ext: "SIPExtension", tenant: "Tenant") -> dict:
    """
    Resolution poste -> compagnie pour le plan d'appel (TASK-S018.5). Noms de champs
    differents entre les deux niveaux (ext.allow_canada vs tenant.default_allow_canada,
    meme principe que voicemail S008.2) donc resolution explicite plutot que
    resolve_setting() generique (qui suppose un getattr uniforme).
    """
    return {
        "allow_canada": ext.allow_canada if ext.allow_canada is not None else tenant.default_allow_canada,
        "allow_us": ext.allow_us if ext.allow_us is not None else tenant.default_allow_us,
        "allow_international": ext.allow_international if ext.allow_international is not None else tenant.default_allow_international,
        "allow_premium": ext.allow_premium if ext.allow_premium is not None else tenant.default_allow_premium,
        "blocked_countries": ext.blocked_countries or tenant.default_blocked_countries or "",
        "blocked_prefixes": ext.blocked_prefixes or tenant.default_blocked_prefixes or "",
        "ld_pin": decrypt(ext.ld_pin) if ext.ld_pin else (decrypt(tenant.default_ld_pin) if tenant.default_ld_pin else None),
        "ld_monthly_limit": ext.ld_monthly_limit if ext.ld_monthly_limit is not None else tenant.default_ld_monthly_limit,
    }


async def _call_permission_gate_entries(
    caller_ext: "SIPExtension | None", tenant: "Tenant | None", out_routes: list, account: str, db: AsyncSession,
) -> str:
    """
    Entrees de REJET (+ 1 entree de contournement par NIP) evaluees AVANT les routes
    sortantes (TASK-S018.5). FreeSWITCH s'arrete a la premiere <condition> qui matche
    dans un contexte -- les placer avant _outbound_dialplan_entries() dans le document
    suffit a les faire gagner sur la route qui bridgerait sinon l'appel. `call_permission`
    (S018.3) etait stocke mais jamais verifie ; ceci le cable reellement, avec les champs
    granulaires Canada/US/international/premium/pays-prefixes-bloques/NIP/limite ajoutes
    dans cette meme tache.
    """
    if not caller_ext or not tenant:
        return ""
    perm = _resolve_call_permission(caller_ext, tenant)
    entries: list[str] = []

    def _reject(name: str, expr: str) -> str:
        return f'''      <extension name="{name}">
        <condition field="destination_number" expression="{expr}">
          <action application="respond" data="403 Forbidden"/>
        </condition>
      </extension>'''

    # --- NIP d'autorisation : composer *80<NIP><numero> outrepasse TOUS les blocages
    # ci-dessous (simplification assumee -- pas de bypass partiel par categorie). Le
    # NIP est compile directement dans le motif regenere a chaque lookup xml_curl
    # (jamais ecrit en clair sur disque) ; bridge fait directement ici (pas de
    # "transfer" -- un transfer redeclencherait un lookup xml_curl sur le numero nu,
    # qui repasserait par ces memes portes et annulerait le contournement).
    if perm["ld_pin"] and out_routes:
        trunk_id = caller_ext.preferred_trunk_id or out_routes[0].trunk_id
        gw_name = xe(f"{account}-gw-{str(trunk_id)[:8]}")
        entries.append(f'''      <!-- NIP d'autorisation interurbain -->
      <extension name="ld_pin_override">
        <condition field="destination_number" expression="^\\*80{re.escape(perm['ld_pin'])}([0-9]+)$">
          <action application="set" data="outbound_caller_id_number=${{caller_id_number}}"/>
          <action application="bridge" data="sofia/gateway/{gw_name}/$1"/>
        </condition>
      </extension>''')

    # --- Limite mensuelle (cout CDR cumule depuis le 1er du mois courant, meme
    # source que le module facturation -- pas de compteur separe a resynchroniser) ---
    if perm["ld_monthly_limit"] is not None:
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.coalesce(func.sum(CDR.cost), 0)).where(
                CDR.tenant_id == tenant.id,
                CDR.src == caller_ext.username,
                CDR.start_time >= month_start,
            )
        )
        spent = float(result.scalar() or 0)
        if spent >= float(perm["ld_monthly_limit"]):
            entries.append(_reject("ld_limit_exceeded", "^(011.+|1?[2-9][0-9]{9})$"))

    # --- Categories NANP ---
    canada_alt = "|".join(sorted(CANADIAN_AREA_CODES))
    if not perm["allow_premium"]:
        entries.append(_reject("perm_premium", "^1?900[0-9]{7}$"))
    if not perm["allow_international"]:
        entries.append(_reject("perm_international", "^011([0-9]+)$"))
    else:
        for code in [c.strip() for c in perm["blocked_countries"].split(",") if c.strip()]:
            entries.append(_reject(f"perm_blocked_country_{xe(code)}", f"^011{re.escape(code)}"))
    if not perm["allow_canada"]:
        entries.append(_reject("perm_canada", f"^1?({canada_alt})[2-9][0-9]{{6}}$"))
    if not perm["allow_us"]:
        entries.append(_reject("perm_us", f"^1?(?!({canada_alt}))[2-9][0-9]{{2}}[2-9][0-9]{{6}}$"))
    for prefix in [p.strip() for p in perm["blocked_prefixes"].split(",") if p.strip()]:
        entries.append(_reject(f"perm_blocked_prefix_{xe(prefix)}", f"^{re.escape(prefix)}"))

    return "\n\n".join(entries)


def _outbound_dialplan_entries(routes: list, account: str, caller_ext: "SIPExtension | None" = None) -> str:
    # Enregistrement automatique "externe sortant" (TASK-023.4).
    record_action = _record_action(bool(caller_ext and caller_ext.record_external_outgoing))
    entries = []
    for route in routes:
        patterns = [p.strip() for p in (route.dial_patterns or "").split(",") if p.strip()]
        for pattern in patterns:
            # Convert NANP patterns to regex
            regex = _pattern_to_regex(pattern)
            strip = route.strip_digits or 0
            prepend = xe(route.prepend_digits or "")
            gw_name = xe(f"{account}-gw-{str(route.trunk_id)[:8]}")
            route_name = xe(f"outbound_{route.name}_{pattern}")

            strip_action = ""
            if strip > 0:
                strip_action = f'\n          <action application="set" data="effective_caller_id_number=${{caller_id_number}}"/>'

            entries.append(f"""      <!-- Outbound: {xe(route.name)} pattern {xe(pattern)} -->
      <extension name="{route_name}">
        <condition field="destination_number" expression="{xe(regex)}">
          <action application="set" data="outbound_caller_id_number=${{caller_id_number}}"/>{strip_action}{record_action}
          <action application="bridge" data="sofia/gateway/{gw_name}/{prepend}$1"/>
        </condition>
      </extension>""")
    return "\n\n".join(entries)


def _pattern_to_regex(pattern: str) -> str:
    """Convert Asterisk-style dial pattern to FreeSWITCH regex."""
    if pattern.endswith("."):
        # Strip trailing dot wildcard — match one or more
        base = pattern[:-1]
        base = base.replace("N", "[2-9]").replace("X", "[0-9]").replace("Z", "[1-9]")
        return f"^{base}(.+)$"
    p = pattern.replace("N", "[2-9]").replace("X", "[0-9]").replace("Z", "[1-9]")
    return f"^({p})$"


async def _dialplan_public(destination: str, db: AsyncSession) -> Response:
    """
    Dialplan for inbound calls from trunks (context=public).
    Matches DID number → routes to extension, IVR, or voicemail.
    """
    # Normalize DID: try with and without leading 1
    dids_to_try = [destination]
    if destination.startswith("1") and len(destination) == 11:
        dids_to_try.append(destination[1:])
    elif len(destination) == 10:
        dids_to_try.append("1" + destination)

    result = await db.execute(
        select(InboundRoute)
        .join(Tenant, InboundRoute.tenant_id == Tenant.id)
        .where(
            InboundRoute.did_number.in_(dids_to_try),
            InboundRoute.is_active == True,
            Tenant.is_active == True,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        return _resp(NOT_FOUND)

    # Get tenant for domain name
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == route.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        return _resp(NOT_FOUND)

    domain = xe(tenant.account_number)
    dest_num = xe(destination)
    actions = await _inbound_actions(route, tenant, db)

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="public">

      <extension name="inbound_{dest_num}">
        <condition field="destination_number" expression="^{dest_num}$">
          <action application="set" data="domain_name={domain}"/>
{actions}
        </condition>
      </extension>

    </context>
  </section>
</document>"""
    return _resp(xml)


async def _inbound_actions(route: "InboundRoute", tenant: "Tenant", db: AsyncSession) -> str:
    """Generate dialplan actions for an inbound route destination."""
    domain = tenant.account_number
    dest_type = route.destination_type
    dest = route.destination

    if dest_type == "extension":
        bridge = _bridge(dest, domain)
        # Enregistrement automatique "externe entrant" (TASK-023.4) -- depend du poste
        # DESTINATAIRE (celui qui recoit l'appel externe), pas d'un poste "appelant"
        # puisque l'appelant est externe (pas un de nos postes).
        dest_result = await db.execute(
            select(SIPExtension).where(SIPExtension.username == dest, SIPExtension.is_active == True)
        )
        dest_ext = dest_result.scalar_one_or_none()
        record_action = _record_action(bool(dest_ext and dest_ext.record_external_incoming))
        return f"""          <action application="set" data="ringback=${{us-ring}}"/>{record_action}
          <action application="bridge" data="{xe(bridge)}"/>"""

    if dest_type == "ivr":
        # dest = IVR UUID or name
        ivr_menu_name = xe(f"ivr_{dest}")
        return f"""          <action application="answer"/>
          <action application="sleep" data="1000"/>
          <action application="ivr" data="{ivr_menu_name}"/>"""

    if dest_type == "queue":
        queue_name = xe(dest)
        return f"""          <action application="answer"/>
          <action application="sleep" data="1000"/>
          <action application="callcenter" data="{queue_name}@default"/>"""

    if dest_type == "voicemail":
        return f"""          <action application="answer"/>
          <action application="voicemail" data="default ${{domain_name}} {xe(dest)}"/>"""

    if dest_type == "hangup":
        return '          <action application="hangup" data="CALL_REJECTED"/>'

    return '          <action application="hangup" data="UNALLOCATED_NUMBER"/>'


# ── CONFIGURATION (IVR menus) ─────────────────────────────────────────────────

async def _handle_configuration(form, db: AsyncSession) -> Response:
    """
    Return module configuration XML.
    Currently handles: ivr.conf (IVR menus).
    """
    key_value = form.get("key_value", "")

    if key_value == "ivr.conf":
        return await _config_ivr(db)

    return _resp(NOT_FOUND)


async def _config_ivr(db: AsyncSession) -> Response:
    """
    Return ivr.conf with all active IVR menus across all tenants.
    FreeSWITCH calls this when the `ivr` dialplan application runs.
    """
    result = await db.execute(
        select(IVR)
        .where(IVR.is_active == True)
        .options(selectinload(IVR.options))
    )
    ivrs = result.scalars().all()

    menus_xml = ""
    for ivr in ivrs:
        menu_name = xe(f"ivr_{ivr.id}")
        greeting = xe(ivr.greeting_text or "ivr/ivr-welcome.wav")
        timeout_ms = (ivr.timeout_seconds or 10) * 1000
        max_fail = ivr.max_retries or 3

        # Get tenant for domain
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == ivr.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        domain = tenant.account_number if tenant else ""

        options_xml = ""
        for opt in sorted(ivr.options, key=lambda o: o.digit):
            action_param = _ivr_option_action(opt, domain)
            options_xml += f"""      <entry action="menu-exec-app" digits="{xe(opt.digit)}" param="{xe(action_param)}"/>\n"""

        menus_xml += f"""    <menu name="{menu_name}"
          greet-long="{greeting}"
          greet-short="{greeting}"
          invalid-sound="ivr/ivr-that_was_an_invalid_entry.wav"
          exit-sound="voicemail/vm-goodbye.wav"
          timeout="{timeout_ms}"
          max-failures="{max_fail}"
          max-timeouts="{max_fail}">
{options_xml}    </menu>\n"""

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="configuration">
    <configuration name="ivr.conf" description="IVR menus">
      <menus>
{menus_xml}      </menus>
    </configuration>
  </section>
</document>"""
    return _resp(xml)


def _ivr_option_action(opt: "IVROption", domain: str) -> str:
    """Generate the FreeSWITCH menu entry param for an IVR option."""
    if opt.destination_type == "extension":
        bridge = _bridge(opt.destination, domain)
        return f"bridge {bridge}"
    if opt.destination_type == "ivr":
        return f"ivr ivr_{opt.destination}"
    if opt.destination_type == "voicemail":
        return f"voicemail default ${{domain_name}} {opt.destination}"
    if opt.destination_type == "queue":
        return f"callcenter {opt.destination}@default"
    return "hangup NORMAL_CLEARING"
