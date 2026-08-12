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
import json
import random
import re
import uuid as uuid_mod
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.crypto import decrypt
from app.core.nanp import CANADIAN_AREA_CODES
from app.core.esl import get_esl
from app.models.tenant import Tenant
from app.models.sip import SIPExtension, TenantDID
from app.models.dialplan import InboundRoute, OutboundRoute
from app.models.ivr import IVR, IVROption, RingGroup, PagingGroup, PagingGroupMember
from app.models.cdr import CDR
from app.models.voicemail import VoicemailBox
from app.models.prompt import AudioPrompt
from app.core.local_stream import MOH_SOUNDS_BASE

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


# ⚠️ TASK-023.33 : domaine d'enregistrement/bridge FIXE, le meme pour TOUS les
# tenants -- demande explicite de l'utilisateur ("aucun serveur SIP marche avec
# ta technique de tenant dans serveur"). Le tenant est identifie UNIQUEMENT par le
# username (deja globalement unique, prefixe "{account}-"), jamais par le domaine
# que le telephone envoie dans son champ SIP Server -- celui-ci peut etre une IP,
# un DNS, ou n'importe quoi, ca n'a plus d'importance. Doit matcher EXACTEMENT
# force-register-domain / force-register-db-domain sur le profil sofia "internal"
# (sinon les cibles de bridge "user/{username}@{domain}" ne trouveraient plus
# l'enregistrement, verifie contre sofia_reg.c : reg_db_domain determine la cle de
# stockage reelle). Ne remplace PAS `_context_name()` (routage dialplan par tenant,
# aucun lien avec le domaine d'enregistrement).
REG_DOMAIN = "sipv"

# TASK-S046/S047 -- meme repertoire que prompts.py::UPLOAD_DIR, duplique ici en
# string simple (ce fichier n'a pas besoin de manipuler le filesystem, juste de
# construire le chemin passe a `playback` pour FreeSWITCH).
PROMPT_DIR = "/home/sipv/sipv/backend/uploads/audio_prompts"


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
        if not ext and tenant and form.get("action") == "voicemail-lookup":
            # ⚠️ Bug corrige (TASK-S023.31 suite) : l'annonce generique de la BV
            # ("the person at extension...") parlait le USERNAME SIP complet
            # (ex: "t1001-100") au lieu du simple numero de poste (ex: "100") --
            # demande explicite de Philippe. Le mailbox passe a l'app voicemail()
            # est maintenant le numero nu (voir _ext_dialplan_entries etc.), donc
            # la propre requete interne de mod_voicemail (action=voicemail-lookup)
            # doit pouvoir matcher par NUMERO D'EXTENSION plutot que par username
            # complet. Scope AU TENANT DEJA RESOLU par le domaine (jamais actif
            # pour un vrai REGISTER, qui envoie toujours le username complet et
            # matche donc deja plus haut) -- pas de risque d'ambiguite inter-tenant.
            fallback = await db.execute(
                select(SIPExtension).where(
                    SIPExtension.extension == username,
                    SIPExtension.tenant_id == tenant.id,
                    SIPExtension.is_active == True,
                )
            )
            ext = fallback.scalar_one_or_none()
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
        vm_box = None
        if ext.voicemail_enabled:
            vm_result = await db.execute(select(VoicemailBox).where(VoicemailBox.extension_id == ext.id))
            vm_box = vm_result.scalar_one_or_none()
        # ⚠️ Bug corrige (TASK-023.29) : mod_voicemail fait sa PROPRE requete directory
        # (action=voicemail-lookup, verifie dans le source) pour retrouver le
        # PROPRIETAIRE de la boite (ex: t1001-101), PENDANT le depot d'un appel EXTERNE
        # deja en cours -- FreeSWITCH merge alors les <variables> de cette reponse sur
        # le CANAL DE L'APPELANT en cours, ecrasant son vrai effective_caller_id_number
        # (ex: le cellulaire "15148039411") par celui du proprietaire de boite (ex: "101").
        # Confirme en direct : sujet de courriel affichait le # du poste, pas le # de
        # l'appelant. Pour cette requete specifique, on renvoie SEULEMENT les <params>
        # (password/vm-*), jamais de <variables> -- rien a merger sur un canal etranger.
        if form.get("action") == "voicemail-lookup":
            return _resp(_directory_voicemail_lookup_user(tenant, ext, advertised_domain=domain, vm_box=vm_box))
        return _resp(_directory_single_user(tenant, ext, advertised_domain=domain, vm_box=vm_box))

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
# Lie la "langue du poste" (catalogue d'options telephonie, meme cle "language"
# que P1362, TASK-S011.5/S044) aux annonces vocales FreeSWITCH -- demande de
# Philippe (2026-08-03) : "on va lier les 2". Valeurs = dossiers reellement
# installes sous sounds/ (verifie sur le serveur : en/us/callie deja present,
# fr/ca/june installe le meme jour, pack officiel FreeSWITCH). "auto" ou valeur
# absente/inconnue -> pas de variable posee, le defaut global (en/us/callie,
# vars.xml) s'applique tel quel.
# Portee volontairement limitee au niveau Tenant.phone_option_defaults (deja
# charge, zero requete supplementaire) -- PAS la chaine complete a 5 niveaux
# (TASK-S044) : _handle_directory est appele a CHAQUE REGISTER/INVITE
# authentifie, un chemin sensible a la performance ou personne n'a encore
# demande de precision par poste pour les annonces vocales (contrairement au
# texte affiche a l'ecran, ou TASK-S044 reste la source de verite).
_LANGUAGE_PROMPT_MAP = {
    "fr": ("fr", "ca", "june"),
    "en": ("en", "us", "callie"),
}


def _user_xml(ext: "SIPExtension", tenant: "Tenant", vm_box: "VoicemailBox | None" = None) -> str:
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
    # TASK-S033 : MOH par tenant -- ${hold_music} regle ici s'applique a la mise
    # en attente normale d'un appel (touche/softkey "Hold"), PAS a la musique
    # d'attente d'une file (mod_callcenter, qui necessite callcenter.conf.xml,
    # jamais genere dans ce projet -- voir TASKSIPV.md TASK-S033 pour le detail
    # de cette limite). Verifie simplement par presence du fragment
    # local_stream genere (regenerate_tenant_moh_stream) -- pas de requete DB
    # ici, cette fonction est appelee a chaque REGISTER.
    # TASK-S033/S058 : hold_music lit DIRECTEMENT le(s) fichier(s) MOH synchronises
    # par regenerate_tenant_moh_stream (dossier "000_...", "001_..." par
    # sort_order, meme dossier que local_stream, deja lisible par freeswitch) --
    # PAS local_stream://, qui est un flux radio PARTAGE en boucle continue
    # (demande explicite de l'utilisateur : local_stream = pour une radio IP,
    # pas pour ca -- chaque appel doit repartir du debut, ce que local_stream ne
    # peut jamais faire puisque tous les auditeurs tombent la ou le flux en est
    # rendu). file_string:// (verifie dans le source FreeSWITCH, mod_dptools.c,
    # file_string_file_open) chaine plusieurs fichiers avec "!" en une seule
    # lecture qui repart TOUJOURS du debut a chaque playback() -- rejoue a
    # CHAQUE Hold ET a chaque nouvel appel. silence_stream://500 = 0.5s de
    # silence avant le debut ("ca commence trop raide").
    # tenant.moh_shuffle=false (Liste) -> tous les fichiers enchaines dans
    # l'ordre choisi. tenant.moh_shuffle=true (Aleatoire) -> un seul fichier
    # tire au hasard parmi la selection, choisi a nouveau a CHAQUE REGISTER.
    hold_music_var = ""
    tenant_moh_dir = MOH_SOUNDS_BASE / domain
    moh_files = sorted(tenant_moh_dir.glob("*.wav")) if tenant_moh_dir.is_dir() else []
    if moh_files:
        if tenant.moh_shuffle:
            chosen = [random.choice(moh_files)]
        else:
            chosen = moh_files
        chain = "!".join(str(f) for f in chosen)
        hold_music_var = f'\n                <variable name="hold_music" value="file_string://silence_stream://500!{xe(chain)}"/>'
    lang_var = ""
    lang_key = (tenant.phone_option_defaults or {}).get("language")
    if lang_key in _LANGUAGE_PROMPT_MAP:
        lang, dialect, voice = _LANGUAGE_PROMPT_MAP[lang_key]
        lang_var = (
            f'\n                <variable name="default_language" value="{lang}"/>'
            f'\n                <variable name="default_dialect" value="{dialect}"/>'
            f'\n                <variable name="default_voice" value="{voice}"/>'
            f'\n                <variable name="sound_prefix" value="$${{sounds_dir}}/{lang}/{dialect}/{voice}"/>'
        )
    # Masquer le caller ID -- applique seulement au sortant externe (outbound_*),
    # jamais au interne (effective_*) : un collegue doit toujours voir qui appelle.
    privacy_var = ""
    if ext.hide_caller_id:
        privacy_var = '\n                <variable name="origination_privacy" value="hide_name:hide_number:screen"/>'
    # Parametres natifs mod_voicemail (TASK-023.29) : mod_voicemail fait SA PROPRE
    # requete "directory" (memes section/champs que le REGISTER, verifie en direct --
    # ni le mot de passe ni l'email ne viennent d'une table separee) pour retrouver
    # vm-password/vm-mailto/vm-email-all-messages/vm-attach-file/vm-skip-instructions
    # sur CE user directory -- notre table VoicemailBox (email, delete_after_email,
    # attach_message, skip_instructions) n'est jamais lue par FreeSWITCH directement,
    # elle sert juste a piloter CES parametres.
    # ⚠️ Bug corrige (verifie contre le SOURCE FreeSWITCH, src/mod/applications/
    # mod_voicemail/mod_voicemail.c) : vm-mailto/vm-email-all-messages/vm-attach-file/
    # vm-skip-instructions sont lus UNIQUEMENT depuis <params> (boucle sur x_user/
    # "params"/"param"), PAS depuis <variables> -- les avoir mis sous <variables> les
    # rendait invisibles a mod_voicemail : le message se deposait bien (mailbox
    # trouvee, MWI mis a jour) mais AUCUN email n'etait jamais tente (confirme par
    # l'absence totale de log postfix apres un depot reel le 2026-07-24).
    vm_params = ""
    if vm_box:
        vm_params = f'\n                <param name="vm-password" value="{xe(vm_box.password)}"/>'
        if vm_box.email and vm_box.email_on_new:
            vm_params += (
                f'\n                <param name="vm-mailto" value="{xe(vm_box.email)}"/>'
                f'\n                <param name="vm-email-all-messages" value="true"/>'
                f'\n                <param name="vm-attach-file" value="{"true" if vm_box.attach_message else "false"}"/>'
            )
        if vm_box.skip_instructions:
            vm_params += '\n                <param name="vm-skip-instructions" value="true"/>'
    return f"""            <user id="{xe(ext.username)}">
              <params>
                <param name="password" value="{xe(decrypt(ext.password))}"/>{vm_params}
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
                <variable name="rtp_secure_media" value="forbidden"/>{lang_var}{hold_music_var}
              </variables>
            </user>"""


def _directory_voicemail_lookup_user(tenant: "Tenant", ext: "SIPExtension", advertised_domain: str | None = None, vm_box: "VoicemailBox | None" = None) -> str:
    """
    Reponse directory MINIMALE pour la requete interne de mod_voicemail
    (action=voicemail-lookup, TASK-023.29) : seulement les <params> vm-* dont
    mod_voicemail a besoin, JAMAIS de <variables> -- voir le bug documente dans
    _handle_directory juste au-dessus de l'appel a cette fonction.
    """
    domain = xe(advertised_domain or tenant.account_number)
    vm_params = ""
    if vm_box:
        vm_params = f'\n                <param name="vm-password" value="{xe(vm_box.password)}"/>'
        if vm_box.email and vm_box.email_on_new:
            vm_params += (
                f'\n                <param name="vm-mailto" value="{xe(vm_box.email)}"/>'
                f'\n                <param name="vm-email-all-messages" value="true"/>'
                f'\n                <param name="vm-attach-file" value="{"true" if vm_box.attach_message else "false"}"/>'
            )
        if vm_box.skip_instructions:
            vm_params += '\n                <param name="vm-skip-instructions" value="true"/>'
    return f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="{domain}">
      <groups>
        <group name="default">
          <users>
            <user id="{xe(ext.username)}">
              <params>{vm_params}
              </params>
            </user>
          </users>
        </group>
      </groups>
    </domain>
  </section>
</document>"""


def _directory_single_user(tenant: "Tenant", ext: "SIPExtension", advertised_domain: str | None = None, vm_box: "VoicemailBox | None" = None) -> str:
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
{_user_xml(ext, tenant, vm_box)}
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
    public / sipv-external → inbound DID routing (from trunks). "public" garde pour
                           compat mais ne sera JAMAIS reellement demande par
                           FreeSWITCH pour le profil external (voir sipv-external
                           ci-dessous) -- collision avec dialplan/public.xml
                           statique (meme piege deja rencontre et corrige pour le
                           profil internal, TASK-S036 point 10).
    sipv-internal       → contexte reel du profil sofia "internal" (voir internal.xml) ;
                           le tenant est determine ICI, au debut du routage, via le
                           domaine d'origine de l'appelant (variable_sip_from_host) —
                           pas via une variable per-user qui ne se propage pas de facon fiable
    sipv-external       → contexte reel du profil sofia "external" (TASK-023.27,
                           premier trunk PSTN reel) -- renomme depuis "public" pour
                           la MEME raison que sipv-internal : dialplan/public.xml
                           (fichier statique vanilla) est prioritaire sur mod_xml_curl
                           pour le contexte "public", ce qui aurait empeche tout
                           appel entrant reel d'atteindre notre backend.
    """
    context = form.get("Caller-Context") or form.get("context", "")
    destination = form.get("Caller-Destination-Number") or form.get("destination_number", "")

    if context.startswith("internal-"):
        account = context[len("internal-"):]
        return await _dialplan_internal(account, destination, db, requested_context=context)

    if context in ("public", "sipv-external"):
        return await _dialplan_public(destination, db, requested_context=context)

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

    # Ring groups (ring_members + failover_steps eager-charge -- TASK-023.9, TASK-S051)
    result = await db.execute(
        select(RingGroup).options(selectinload(RingGroup.ring_members), selectinload(RingGroup.failover_steps)).where(
            RingGroup.tenant_id == tenant.id,
            RingGroup.is_active == True,
        )
    )
    ring_groups = result.scalars().all()

    # Paging groups (TASK-023.23)
    result = await db.execute(
        select(PagingGroup).options(selectinload(PagingGroup.paging_members).selectinload(PagingGroupMember.extension)).where(
            PagingGroup.tenant_id == tenant.id,
            PagingGroup.is_active == True,
        )
    )
    paging_groups = result.scalars().all()

    # Outbound routes (ordered by priority)
    result = await db.execute(
        select(OutboundRoute).where(
            OutboundRoute.tenant_id == tenant.id,
            OutboundRoute.is_active == True,
        ).order_by(OutboundRoute.priority)
    )
    out_routes = result.scalars().all()

    ctx = xe(requested_context or f"internal-{account}")
    domain = REG_DOMAIN
    ext_entries = _ext_dialplan_entries(extensions, domain, account, ctx, caller_ext)
    rg_entries = await _ringgroup_dialplan_entries(ring_groups, domain, extensions, db, ctx, account)
    paging_entries = _paging_dialplan_entries(paging_groups, domain)
    gate_entries = await _call_permission_gate_entries(caller_ext, tenant, out_routes, account, db)
    outbound_entries = _outbound_dialplan_entries(out_routes, account, caller_ext)
    pickup_entries = await _pickup_dialplan_entries(caller_ext, extensions)

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="{ctx}">

      <!-- Voicemail check: *97 -->
      <extension name="voicemail_check">
        <condition field="destination_number" expression="^\\*97$">
          <action application="answer"/>
          <action application="set" data="domain_name={xe(account)}"/>
          <action application="voicemail" data="check default ${{domain_name}} ${{caller_id_number}}"/>
        </condition>
      </extension>

      <!-- Voicemail direct: *98+extension -->
      <extension name="voicemail_direct">
        <condition field="destination_number" expression="^\\*98([0-9]+)$">
          <action application="answer"/>
          <action application="set" data="domain_name={xe(account)}"/>
          <action application="voicemail" data="default ${{domain_name}} $1"/>
        </condition>
      </extension>

{pickup_entries}
{ext_entries}
{rg_entries}
{paging_entries}
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
        # numero nu (ex: "100"), jamais le username SIP complet -- demande
        # explicite de Philippe (TASK-S023.31 suite) : l'annonce generique de
        # la BV doit dire "100", pas "t1001-100".
        target = value or ext.extension
        # ⚠️ Bug corrige (TASK-S023.31) : domain_name jamais pose avant d'appeler
        # l'app voicemail -- mod_voicemail recevait un domaine vide, echouait a
        # localiser le compte (jouait juste "vm-person"+"vm-goodbye" et
        # raccrochait, sans jamais annoncer le nom, sonner le bip, ni permettre
        # d'enregistrer). Confirme en direct dans les logs FreeSWITCH reels
        # (poste 100) : `voicemail(default  t1001-100)` -- double espace =
        # ${{domain_name}} vide.
        return f'<action application="set" data="domain_name={xe(account)}"/><action application="voicemail" data="default ${{domain_name}} {xe(target)}"/>'
    if dest_type == "extension" and value:
        return f'<action application="bridge" data="{_bridge(f"{account}-{value}", domain)}"/>'
    if dest_type == "ring_group" and value:
        return f'<action application="execute_extension" data="{xe(f"rg_{value}")} XML {ctx}"/>'
    return None


async def _pickup_dialplan_entries(caller_ext: "SIPExtension | None", extensions: list) -> str:
    """
    TASK-023.15 : prefixe d'interception *8 -- decroche l'appel en train de sonner
    dans le meme groupe d'interception (pickup_group) que le poste appelant.
    Resolu au moment de la generation XML (pas de cache xml_curl) : interroge ESL
    pour trouver un canal RINGING dont le callee appartient au meme pickup_group,
    puis emet <action application="intercept"> avec l'UUID reel de ce canal.
    Aucune entree emise si le poste appelant n'a pas de pickup_group / n'a pas le
    droit d'intercepter -- *8 tombe alors sur le catchall (486) comme avant.
    """
    if not caller_ext or not caller_ext.pickup_group or not caller_ext.can_intercept_calls:
        return ""
    group_usernames = {e.username for e in extensions if e.pickup_group == caller_ext.pickup_group}
    if not group_usernames:
        return ""
    try:
        esl = await get_esl()
        raw = await esl.show_channels()
        data = json.loads(raw)
    except Exception:
        return ""
    target_uuid = None
    for row in data.get("rows", []):
        if (row.get("callstate") or "").upper() not in ("RINGING", "EARLY"):
            continue
        haystack = " ".join(str(row.get(f, "") or "") for f in (
            "cid_num", "dest", "callee_num", "presence_id", "initial_dest",
        ))
        if any(u in haystack for u in group_usernames):
            target_uuid = row.get("uuid")
            break
    if not target_uuid:
        return ""
    return f"""      <!-- Interception de groupe : *8 -->
      <extension name="call_pickup">
        <condition field="destination_number" expression="^\\*8$">
          <action application="intercept" data="{xe(target_uuid)}"/>
        </condition>
      </extension>"""


def _resolve_alert_info(ext: "SIPExtension", caller_number: str | None) -> str | None:
    """
    Resout la valeur Alert-Info a envoyer pour un appel interne vers `ext` (TASK-023.12).
    Priorite : silencieux > regle caller ID > sonnerie interne specifique > sonnerie
    distinctive generale (S018.3). Retourne None si rien de configure (aucun header
    ajoute -- comportement identique a avant cette tache).
    """
    if ext.silent_ring:
        return "silent"
    if ext.caller_id_ring_rules and caller_number:
        for rule in ext.caller_id_ring_rules.split(","):
            if ":" not in rule:
                continue
            pattern, ring = rule.split(":", 1)
            pattern = pattern.strip()
            if pattern and pattern in caller_number:
                return ring.strip()
    if ext.ring_internal:
        return ext.ring_internal
    return ext.distinctive_ring or None


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
        # TASK-S058 : rtp_secure_media reste "mandatory" pour ETABLIR l'appel (directory
        # XML, xml_curl.py::_user_xml) -- ici, une fois record_session() deja fait
        # (donc apres la negociation initiale des DEUX legs), on relache a "optional"
        # sur les DEUX legs (export = courant + b-leg origine juste apres) pour que
        # les re-INVITE ulterieurs (Hold, entre autres) ne se fassent plus rejeter en
        # 488 "Crypto not negotiated but required" quand le telephone ne reoffre pas
        # le SRTP dessus. execute_on_answer (tente avant) s'est avere peu fiable en
        # test reel (marche sur un leg, pas l'autre, dans le meme appel) -- ceci est
        # deterministe, place directement dans le dialplan.
        hold_crypto_relax = ''


        # --- TASK-023.6 : renvoi immediat / DND -- le poste ne sonne PAS du tout,
        # redirige tout de suite. Ne change RIEN pour un poste sans renvoi/DND actif
        # (comportement identique a avant cette tache -- verifie explicitement pour
        # ne pas casser les postes existants qui n'ont ni l'un ni l'autre configure).
        diversion = None
        if ext.forward_immediate_enabled:
            diversion = _forward_action_xml(ext.forward_immediate_destination_type, ext.forward_immediate_destination, ext, domain, account, ctx)
        elif ext.dnd_enabled:
            # DND sans renvoi immediat configure -- va a la boite vocale si activee, sinon occupe.
            # ⚠️ Bug corrige (TASK-S023.31) : domain_name jamais pose, voir vm_action plus bas.
            diversion = ('<action application="set" data="domain_name=' + xe(account) + '"/>'
                         '<action application="voicemail" data="default ${domain_name} ' + xe(ext.extension) + '"/>') if ext.voicemail_enabled else '<action application="respond" data="486 Busy Here"/>'

        if diversion:
            entries.append(f"""      <!-- Extension {ext.extension}: {xe(ext.name)} (renvoi immediat/DND) -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">{record_action}
          {diversion}
        </condition>
      </extension>""")
            continue

        bridge = _bridge(ext.username, domain)
        if ext.auto_answer_enabled:
            # Intercom auto-answer -- Call-Info;answer-after=0 est la convention SIP
            # standard reconnue par la plupart des telephones de bureau (Grandstream,
            # Polycom, Yealink) pour l'auto-reponse "intercom". Verifie structurellement
            # (le header apparait bien dans le bridge genere) mais PAS avec un vrai
            # appel decroche automatiquement sur un telephone physique (TASK-023.11 --
            # aurait demande de faire sonner/repondre reellement le GXP2135 de test
            # sans confirmation prealable de l'utilisateur, pas fait a la sauvette).
            # intercom_warning_tone/intercom_mic_muted_on_answer restent stockes mais
            # PAS cables (necessiteraient un script post-reponse par uuid, pas encore
            # de mecanisme etabli dans ce projet pour ca).
            bridge = f"{{sip_h_Call-Info=<sip:intercom>;answer-after=0}}{bridge}"
        else:
            # --- TASK-023.12 : sonnerie interne / silencieuse / regle par caller ID ---
            # Alert-Info est un header SIP standard -- c'est le TELEPHONE (Grandstream/
            # Polycom/etc.) qui decide quelle sonnerie jouer selon sa valeur, FreeSWITCH
            # ne fait que le transmettre. Sans auto-answer (sinon ca ne sonne jamais).
            caller_num = (caller_ext.caller_id_internal_number or caller_ext.caller_id_number or caller_ext.extension) if caller_ext else None
            alert_info = _resolve_alert_info(ext, caller_num)
            if alert_info:
                bridge = f"{{sip_h_Alert-Info=<sip:{xe(alert_info)}>}}{bridge}"
        # ⚠️ Bug corrige (TASK-023.30) : aucun timeout n'etait jamais pose sur le bridge
        # -- `vm_action` (l'action voicemail) n'etait donc JAMAIS atteinte, le bridge
        # sonnait indefiniment jusqu'a ce que l'appelant raccroche lui-meme (confirme
        # en direct : poste 101 sonnait 6+ coups sans jamais tomber sur la BV). Le champ
        # `forward_no_answer_delay_seconds` (defaut modele = 20s) existait deja en base
        # depuis S018.3 mais n'etait jamais lu ici. `forward_no_answer_enabled` (type
        # de destination configurable) est maintenant cable aussi -- s'il est actif on
        # utilise sa destination typee (poste/BV/groupe d'appel), sinon on retombe sur
        # le simple `voicemail_enabled` (comportement historique preserve).
        timeout = ext.forward_no_answer_delay_seconds or 20
        if ext.forward_no_answer_enabled:
            vm_action = _forward_action_xml(ext.forward_no_answer_destination_type, ext.forward_no_answer_destination, ext, domain, account, ctx) or ""
        elif ext.voicemail_enabled:
            # ⚠️ Bug corrige (TASK-S023.31) : domain_name jamais pose avant cette
            # action -- c'est CE chemin precis (poste sonne, pas de reponse,
            # tombe sur la BV) qui echouait en vrai (confirme dans les logs
            # FreeSWITCH reels du poste 100 : voicemail(default  t1001-100),
            # domaine vide -> mod_voicemail incapable de localiser le compte,
            # joue juste "vm-person"+"vm-goodbye" et raccroche -- pas de nom
            # annonce, pas de bip, pas moyen de laisser un message).
            vm_action = f'<action application="set" data="domain_name={xe(account)}"/><action application="voicemail" data="default ${{domain_name}} {xe(ext.extension)}"/>'
        else:
            vm_action = ""
        vm_action_xml = f"\n          {vm_action}" if vm_action else ""

        # TASK-S052 : forward_busy_enabled/forward_offline_enabled etaient stockes
        # depuis S018.3 mais jamais lus ici (meme famille de bug que S047/S048/S051,
        # trouve en auditant sur demande explicite de l'utilisateur 2026-08-07).
        # Purement additif : une extension SANS busy/offline configure passe par
        # EXACTEMENT le meme bloc <condition> unique qu'avant cette tache (zero
        # changement de comportement) -- seule une extension qui active l'un des
        # deux bascule sur la forme multi-condition ci-dessous.
        # ⚠️ [~] Mecanisme ${originate_disposition} + continue="true"/break="on-true"
        # est la technique FreeSWITCH standard documentee pour ce genre de routage
        # (busy/no-answer/offline apres un bridge), et la structure XML generee est
        # verifiee, mais la VALEUR EXACTE de originate_disposition pour chaque cause
        # (USER_BUSY confirme standard ; NO_ROUTE_DESTINATION/SUBSCRIBER_ABSENT/
        # UNALLOCATED_NUMBER pour "poste non enregistre" sont les causes les plus
        # plausibles mais pas confirmees avec un vrai appel/poste eteint dans cette
        # session, aucun softphone disponible). Si aucune des causes ne matche, la
        # derniere <condition> (identique a l'ancien comportement, vm_action) sert
        # de filet de securite -- aucune regression possible meme si les valeurs de
        # disposition exactes s'averent differentes de ce qui est visé ici.
        busy_action = _forward_action_xml(ext.forward_busy_destination_type, ext.forward_busy_destination, ext, domain, account, ctx) if ext.forward_busy_enabled else None
        offline_action = _forward_action_xml(ext.forward_offline_destination_type, ext.forward_offline_destination, ext, domain, account, ctx) if ext.forward_offline_enabled else None

        if busy_action or offline_action:
            extra_conditions = ""
            if busy_action:
                extra_conditions += f"""
        <condition field="${{originate_disposition}}" expression="^USER_BUSY$" break="on-true">
          {busy_action}
        </condition>"""
            if offline_action:
                extra_conditions += f"""
        <condition field="${{originate_disposition}}" expression="^(NO_ROUTE_DESTINATION|SUBSCRIBER_ABSENT|UNALLOCATED_NUMBER)$" break="on-true">
          {offline_action}
        </condition>"""
            fallback_xml = f"\n          {vm_action}" if vm_action else ""
            entries.append(f"""      <!-- Extension {ext.extension}: {xe(ext.name)} (busy/offline) -->
      <extension name="{name}" continue="true">
        <condition field="destination_number" expression="^{num}$" break="never">
          <action application="set" data="ringback=${{us-ring}}"/>{record_action}
          <action application="set" data="hangup_after_bridge=false"/>
          <action application="set" data="call_timeout={timeout}"/>{hold_crypto_relax}
          <action application="bridge" data="{bridge}"/>
        </condition>{extra_conditions}
        <condition field="destination_number" expression="^{num}$">{fallback_xml}
        </condition>
      </extension>""")
            continue

        entries.append(f"""      <!-- Extension {ext.extension}: {xe(ext.name)} -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="ringback=${{us-ring}}"/>{record_action}
          <action application="set" data="call_timeout={timeout}"/>{hold_crypto_relax}
          <action application="bridge" data="{bridge}"/>{vm_action_xml}
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


async def _ringgroup_dialplan_entries(ring_groups: list, domain: str, extensions: list, db: AsyncSession, ctx: str, account: str) -> str:
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

        # TASK-S051 : chaine de destinations de secours illimitee si le groupe ne
        # repond pas -- `hangup_after_bridge=false` (sinon FreeSWITCH raccroche
        # automatiquement des que le premier bridge echoue, comme c'etait le cas
        # avant cette tache : RingGroup.no_answer_destination existait mais n'etait
        # JAMAIS consulte ici, bug trouve en meme temps que cette demande). Chaque
        # etape suivante execute a son tour si la precedente echoue (comportement
        # naturel du dialplan FreeSWITCH : une action qui echoue laisse la main a
        # la suivante dans le meme <condition>).
        failover_actions = ""
        for step in sorted(rg.failover_steps or [], key=lambda s: s.step_order):
            if step.destination_type == "extension":
                step_timeout = xe(str(step.ring_seconds or rg.ring_time))
                # TASK-023.29 : meme convention que _inbound_actions_for -- step.destination
                # est le numero NU du poste ("101"), le prefixe tenant est reconstruit ici.
                step_username = f"{account}-{step.destination}" if not step.destination.startswith(f"{account}-") else step.destination
                failover_actions += f"""
          <action application="set" data="call_timeout={step_timeout}"/>
          <action application="bridge" data="{xe(_bridge(step_username, domain))}"/>"""
            elif step.destination_type == "voicemail":
                failover_actions += f"""
          <action application="voicemail" data="default ${{domain_name}} {xe(step.destination)}"/>"""
            elif step.destination_type == "ivr":
                failover_actions += f"""
          <action application="ivr" data="{xe(f'ivr_{step.destination}')}"/>"""
            elif step.destination_type == "queue":
                failover_actions += f"""
          <action application="callcenter" data="{xe(step.destination)}@default"/>"""
            elif step.destination_type == "hangup":
                failover_actions += """
          <action application="hangup" data="NORMAL_CLEARING"/>"""

        entries.append(f"""      <!-- Ring group {rg.extension}: {xe(rg.name)} -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="hangup_after_bridge=false"/>
          <action application="set" data="call_timeout={timeout}"/>
          <action application="set" data="ringback=${{us-ring}}"/>
          <action application="bridge" data="{xe(bridge_str)}"/>{failover_actions}
          <action application="hangup" data="NORMAL_CLEARING"/>
        </condition>
      </extension>""")
    return "\n\n".join(entries)


def _paging_dialplan_entries(paging_groups: list, domain: str) -> str:
    """
    TASK-023.23 : diffusion (broadcast) vers un groupe de paging -- distinct d'un
    ring group (pas une sonnerie d'appel entrant normale). Cable via `bridge`
    simultane + auto-answer Call-Info (meme technique validee que l'intercom
    S023.11) vers tous les membres `can_receive` -- `page` (app FreeSWITCH dediee
    au paging one-way) N'EST PAS disponible sur ce build (verifie : absent de
    `show application`), donc pas utilisee.
    ⚠️ mode="unidirectional" ne coupe PAS reellement l'audio du recepteur vers
    l'emetteur dans cette implementation -- aucun mecanisme fiable trouve/verifie
    pour ca dans ce projet (documente honnetement plutot que suppose). Les deux
    modes se comportent donc pour l'instant comme un appel diffuse auto-repondu ;
    seul `multicast_address`/`multicast_port` (donnees de provisioning telephone,
    TASK-S011.4) distinguera un jour vraiment le comportement one-way reel, qui se
    passe telephone-a-telephone sur le LAN, hors du chemin media de FreeSWITCH.
    """
    entries = []
    for pg in paging_groups:
        receivers = [m for m in (pg.paging_members or []) if m.can_receive and m.extension]
        if not receivers:
            continue
        name = xe(f"pg_{pg.extension}")
        num = xe(pg.extension)
        targets = ":_:".join(
            f"{{sip_h_Call-Info=<sip:intercom>;answer-after=0}}{_bridge(m.extension.username, domain)}"
            for m in receivers
        )
        entries.append(f"""      <!-- Paging group {pg.extension}: {xe(pg.name)} ({xe(pg.mode)}) -->
      <extension name="{name}">
        <condition field="destination_number" expression="^{num}$">
          <action application="set" data="ringback=${{us-ring}}"/>
          <action application="bridge" data="{targets}"/>
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


async def _dialplan_public(destination: str, db: AsyncSession, requested_context: str = "public") -> Response:
    """
    Dialplan for inbound calls from trunks (context=public / sipv-external).
    Matches DID number → routes to extension, IVR, or voicemail.

    `requested_context` : le <context name="..."> retourne DOIT correspondre
    EXACTEMENT au contexte demande par FreeSWITCH (meme regle deja etablie pour
    _dialplan_internal -- verifie dans switch_xml.c) -- sans ca, un appel entrant
    reel via le profil external (context="sipv-external", TASK-023.27) serait
    rejete comme "not found" meme avec une reponse par ailleurs valide.
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

    dest_num = xe(destination)
    ctx = xe(requested_context)
    actions = await _inbound_actions(route, tenant, db)

    xml = f"""{XML_HDR}
<document type="freeswitch/xml">
  <section name="dialplan">
    <context name="{ctx}">

      <extension name="inbound_{dest_num}">
        <condition field="destination_number" expression="^{dest_num}$">
          <action application="set" data="domain_name={xe(tenant.account_number)}"/>
{actions}
        </condition>
      </extension>

    </context>
  </section>
</document>"""
    return _resp(xml)


async def _inbound_actions(route: "InboundRoute", tenant: "Tenant", db: AsyncSession) -> str:
    """Generate dialplan actions for an inbound route destination -- point d'entree
    depuis _dialplan_public(), delegue a _inbound_actions_for() (TASK-S047)."""
    return await _inbound_actions_for(
        route.destination_type, route.destination, tenant, db,
        after_type=route.after_message_destination_type, after_dest=route.after_message_destination,
    )


async def _inbound_actions_for(
    dest_type: str, dest: str | None, tenant: "Tenant", db: AsyncSession,
    after_type: str | None = None, after_dest: str | None = None,
) -> str:
    """
    ⚠️ TASK-023.29 : `dest` pour "extension"/"voicemail" est desormais
    le SEUL numero de poste (ex: "102"), jamais le username FreeSWITCH complet
    ("t1001-102") -- demande explicite de l'utilisateur ("c'est le poste 102 pas
    t1001-102"), meme convention que `_forward_action_xml` (deja bare+prefixe
    ailleurs dans ce fichier). Le prefixe tenant est reconstruit ICI a partir du
    domaine deja resolu, jamais expose a l'admin/API.

    TASK-S047 : `after_type`/`after_dest` ne sont consultes QUE quand
    dest_type == "message" -- action a executer apres la lecture de la phrase
    ("Ajouter une destination" cote UI). Null = raccrocher (comportement par
    defaut demande par l'utilisateur). Un seul niveau de chainage autorise --
    after_type == "message" est ignore volontairement pour ne jamais boucler.
    """
    account = tenant.account_number
    username = f"{account}-{dest}" if dest and not dest.startswith(f"{account}-") else dest

    if dest_type == "extension":
        bridge = _bridge(username, REG_DOMAIN)
        # Enregistrement automatique "externe entrant" (TASK-023.4) -- depend du poste
        # DESTINATAIRE (celui qui recoit l'appel externe), pas d'un poste "appelant"
        # puisque l'appelant est externe (pas un de nos postes).
        dest_result = await db.execute(
            select(SIPExtension).where(SIPExtension.username == username, SIPExtension.is_active == True)
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
        # numero nu (dest, ex: "102"), pas le username reconstruit -- meme
        # correction que _forward_action_xml (TASK-S023.31 suite).
        return f"""          <action application="answer"/>
          <action application="voicemail" data="default ${{domain_name}} {xe(dest)}"/>"""

    if dest_type == "message":
        try:
            prompt_id = uuid_mod.UUID(dest)
        except (ValueError, TypeError, AttributeError):
            return '          <action application="hangup" data="UNALLOCATED_NUMBER"/>'
        result = await db.execute(
            select(AudioPrompt).where(AudioPrompt.id == prompt_id, AudioPrompt.tenant_id == tenant.id, AudioPrompt.is_active == True)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            return '          <action application="hangup" data="UNALLOCATED_NUMBER"/>'
        playback_path = xe(f"{PROMPT_DIR}/{prompt.filename}")
        actions = f"""          <action application="answer"/>
          <action application="playback" data="{playback_path}"/>\n"""
        if after_type and after_type != "message":
            actions += await _inbound_actions_for(after_type, after_dest, tenant, db)
        else:
            actions += '          <action application="hangup" data="NORMAL_CLEARING"/>'
        return actions

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

    # TASK-S047 : preload en un seul aller-retour DB les prompts assignes comme
    # greeting, plutot qu'une requete par IVR dans la boucle.
    prompt_ids = [ivr.greeting_prompt_id for ivr in ivrs if ivr.greeting_prompt_id]
    prompt_map: dict = {}
    if prompt_ids:
        presult = await db.execute(select(AudioPrompt).where(AudioPrompt.id.in_(prompt_ids), AudioPrompt.is_active == True))
        prompt_map = {p.id: p for p in presult.scalars().all()}

    menus_xml = ""
    for ivr in ivrs:
        menu_name = xe(f"ivr_{ivr.id}")
        prompt = prompt_map.get(ivr.greeting_prompt_id) if ivr.greeting_prompt_id else None
        if prompt:
            greeting = xe(f"{PROMPT_DIR}/{prompt.filename}")
        else:
            greeting = xe(ivr.greeting_text or "ivr/ivr-welcome.wav")
        timeout_ms = (ivr.timeout_seconds or 10) * 1000
        max_fail = ivr.max_retries or 3

        options_xml = ""
        for opt in sorted(ivr.options, key=lambda o: o.digit):
            action_param = _ivr_option_action(opt, REG_DOMAIN)
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
