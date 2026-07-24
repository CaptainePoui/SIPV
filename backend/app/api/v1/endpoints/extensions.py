import logging
import uuid
import secrets
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.audit import log_audit
from app.core import erpcrm_client
from app.core.config import settings
from app.core.crypto import encrypt, decrypt
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.api.v1.endpoints.sync import verify_api_key
from app.models.sip import SIPExtension
from app.models.tenant import Tenant
from app.models.pending_change import PendingChange
from app.models.user import User

router = APIRouter()
logger = logging.getLogger("extensions")


async def _link_erpcrm_contact(ext: SIPExtension) -> uuid.UUID | None:
    """
    Cherche/cree/lie le contact ERPCRM correspondant a cette extension (TASK-S022).
    Best-effort : si ERPCRM est injoignable, l'extension reste creee sans lien —
    le lien pourra etre refait plus tard (pas bloquant pour la creation du poste).
    """
    parts = ext.name.split(maxsplit=1)
    first_name = parts[0] if parts else ext.name
    last_name = parts[1] if len(parts) > 1 else ""
    try:
        contact = await erpcrm_client.search_contact(ext.name)
        if contact:
            await erpcrm_client.update_contact(contact["id"], sipv_sync=True, extension=ext.extension)
            return uuid.UUID(contact["id"])
        contact = await erpcrm_client.create_contact(first_name, last_name, ext.extension)
        return uuid.UUID(contact["id"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.warning("Lien ERPCRM echoue pour extension %s: %s", ext.username, e)
        return None


class ExtOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    extension: str
    name: str
    username: str
    voicemail_enabled: bool
    voicemail_email: str | None
    caller_id_name: str | None
    caller_id_number: str | None
    record_calls: bool
    record_mode: str
    record_internal_incoming: bool
    record_internal_outgoing: bool
    record_external_incoming: bool
    record_external_outgoing: bool
    max_contacts: int
    is_active: bool
    codec_list: str
    transport: str
    schedule_id: uuid.UUID | None
    erpcrm_contact_id: uuid.UUID | None
    freeswitch_synced: bool
    created_at: datetime
    site: str | None
    description: str | None
    display_language: str
    timezone: str | None
    name_override: bool
    call_permission: str
    forward_immediate_enabled: bool
    forward_immediate_destination: str | None
    forward_immediate_destination_type: str
    forward_busy_enabled: bool
    forward_busy_destination: str | None
    forward_busy_destination_type: str
    forward_no_answer_enabled: bool
    forward_no_answer_destination: str | None
    forward_no_answer_destination_type: str
    forward_no_answer_delay_seconds: int | None
    forward_offline_enabled: bool
    forward_offline_destination: str | None
    forward_offline_destination_type: str
    dnd_enabled: bool
    dnd_locked: bool
    auto_answer_enabled: bool
    max_concurrent_calls: int | None
    distinctive_ring: str | None
    pickup_group: str | None
    paging_groups: str | None
    can_intercept_calls: bool
    groups: list[str] = []
    # --- TASK-023.11 : intercom/paging granulaire ---
    intercom_warning_tone: bool
    intercom_mic_muted_on_answer: bool
    paging_priority: int
    paging_allow_send: bool
    paging_allow_receive: bool
    paging_emergency: bool
    multicast_address: str | None
    multicast_port: int | None
    forced_volume: int | None
    # --- TASK-023.12 : sonnerie detaillee ---
    ring_internal: str | None
    ring_external: str | None
    ring_queue: str | None
    silent_ring: bool
    caller_id_ring_rules: str | None
    # --- TASK-S018.5 : plan d'appel (null = herite du Tenant, voir _resolve_call_permission) ---
    allow_canada: bool | None
    allow_us: bool | None
    allow_international: bool | None
    allow_premium: bool | None
    blocked_countries: str | None
    blocked_prefixes: str | None
    has_ld_pin: bool = False  # jamais le NIP en clair dans la fiche
    ld_monthly_limit: float | None
    preferred_trunk_id: uuid.UUID | None
    # --- TASK-018.6 : caller ID interne/externe ---
    caller_id_internal_name: str | None
    caller_id_internal_number: str | None
    caller_id_external_name: str | None
    caller_id_external_number: str | None
    hide_caller_id: bool

class ExtCreate(BaseModel):
    extension: str
    name: str
    voicemail_enabled: bool = True
    voicemail_email: str | None = None
    caller_id_name: str | None = None
    caller_id_number: str | None = None
    record_calls: bool = False
    record_mode: str = "manual"
    record_internal_incoming: bool = False
    record_internal_outgoing: bool = False
    record_external_incoming: bool = False
    record_external_outgoing: bool = False
    max_contacts: int = 1
    codec_list: str = "ulaw,alaw,g722,g729"
    transport: str = "tls"  # udp, tcp, tls
    schedule_id: uuid.UUID | None = None
    password: str | None = None  # auto-generated if not provided
    site: str | None = None
    description: str | None = None
    display_language: str = "fr"
    timezone: str | None = None
    name_override: bool = False
    call_permission: str = "international"  # local, national, international -- pas encore applique par le dialplan
    forward_immediate_enabled: bool = False
    forward_immediate_destination: str | None = None
    forward_immediate_destination_type: str = "extension"
    forward_busy_enabled: bool = False
    forward_busy_destination: str | None = None
    forward_busy_destination_type: str = "extension"
    forward_no_answer_enabled: bool = False
    forward_no_answer_destination: str | None = None
    forward_no_answer_destination_type: str = "voicemail"
    forward_no_answer_delay_seconds: int | None = 20
    forward_offline_enabled: bool = False
    forward_offline_destination: str | None = None
    forward_offline_destination_type: str = "voicemail"
    dnd_enabled: bool = False
    dnd_locked: bool = False
    auto_answer_enabled: bool = False
    max_concurrent_calls: int | None = None
    distinctive_ring: str | None = None
    pickup_group: str | None = None
    paging_groups: str | None = None
    can_intercept_calls: bool = True
    intercom_warning_tone: bool = True
    intercom_mic_muted_on_answer: bool = False
    paging_priority: int = 0
    paging_allow_send: bool = True
    paging_allow_receive: bool = True
    paging_emergency: bool = False
    multicast_address: str | None = None
    multicast_port: int | None = None
    forced_volume: int | None = None
    ring_internal: str | None = None
    ring_external: str | None = None
    ring_queue: str | None = None
    silent_ring: bool = False
    caller_id_ring_rules: str | None = None
    allow_canada: bool | None = None
    allow_us: bool | None = None
    allow_international: bool | None = None
    allow_premium: bool | None = None
    blocked_countries: str | None = None
    blocked_prefixes: str | None = None
    ld_pin: str | None = None  # en clair a l'entree, chiffre avant stockage
    ld_monthly_limit: float | None = None
    preferred_trunk_id: uuid.UUID | None = None
    caller_id_internal_name: str | None = None
    caller_id_internal_number: str | None = None
    caller_id_external_name: str | None = None
    caller_id_external_number: str | None = None
    hide_caller_id: bool = False

class ExtUpdate(BaseModel):
    name: str | None = None
    voicemail_enabled: bool | None = None
    voicemail_email: str | None = None
    caller_id_name: str | None = None
    caller_id_number: str | None = None
    record_calls: bool | None = None
    record_mode: str | None = None
    record_internal_incoming: bool | None = None
    record_internal_outgoing: bool | None = None
    record_external_incoming: bool | None = None
    record_external_outgoing: bool | None = None
    max_contacts: int | None = None
    is_active: bool | None = None
    codec_list: str | None = None
    transport: str | None = None
    schedule_id: uuid.UUID | None = None
    password: str | None = None
    site: str | None = None
    description: str | None = None
    display_language: str | None = None
    timezone: str | None = None
    name_override: bool | None = None
    call_permission: str | None = None
    forward_immediate_enabled: bool | None = None
    forward_immediate_destination: str | None = None
    forward_immediate_destination_type: str | None = None
    forward_busy_enabled: bool | None = None
    forward_busy_destination: str | None = None
    forward_busy_destination_type: str | None = None
    forward_no_answer_enabled: bool | None = None
    forward_no_answer_destination: str | None = None
    forward_no_answer_destination_type: str | None = None
    forward_no_answer_delay_seconds: int | None = None
    forward_offline_enabled: bool | None = None
    forward_offline_destination: str | None = None
    forward_offline_destination_type: str | None = None
    dnd_enabled: bool | None = None
    dnd_locked: bool | None = None
    auto_answer_enabled: bool | None = None
    max_concurrent_calls: int | None = None
    distinctive_ring: str | None = None
    pickup_group: str | None = None
    paging_groups: str | None = None
    can_intercept_calls: bool | None = None
    intercom_warning_tone: bool | None = None
    intercom_mic_muted_on_answer: bool | None = None
    paging_priority: int | None = None
    paging_allow_send: bool | None = None
    paging_allow_receive: bool | None = None
    paging_emergency: bool | None = None
    multicast_address: str | None = None
    multicast_port: int | None = None
    forced_volume: int | None = None
    ring_internal: str | None = None
    ring_external: str | None = None
    ring_queue: str | None = None
    silent_ring: bool | None = None
    caller_id_ring_rules: str | None = None
    allow_canada: bool | None = None
    allow_us: bool | None = None
    allow_international: bool | None = None
    allow_premium: bool | None = None
    blocked_countries: str | None = None
    blocked_prefixes: str | None = None
    ld_pin: str | None = None  # en clair a l'entree, chiffre avant stockage ; "" = retirer le NIP
    ld_monthly_limit: float | None = None
    preferred_trunk_id: uuid.UUID | None = None
    caller_id_internal_name: str | None = None
    caller_id_internal_number: str | None = None
    caller_id_external_name: str | None = None
    caller_id_external_number: str | None = None
    hide_caller_id: bool | None = None


def _out(e: SIPExtension, groups: list[str] | None = None) -> ExtOut:
    return ExtOut(
        id=e.id, tenant_id=e.tenant_id, extension=e.extension, name=e.name,
        username=e.username, voicemail_enabled=e.voicemail_enabled, voicemail_email=e.voicemail_email,
        caller_id_name=e.caller_id_name, caller_id_number=e.caller_id_number,
        record_calls=e.record_calls, record_mode=e.record_mode,
        record_internal_incoming=e.record_internal_incoming, record_internal_outgoing=e.record_internal_outgoing,
        record_external_incoming=e.record_external_incoming, record_external_outgoing=e.record_external_outgoing,
        max_contacts=e.max_contacts,
        is_active=e.is_active, codec_list=e.codec_list, transport=e.transport, schedule_id=e.schedule_id,
        erpcrm_contact_id=e.erpcrm_contact_id,
        freeswitch_synced=e.freeswitch_synced, created_at=e.created_at,
        site=e.site, description=e.description,
        display_language=e.display_language, timezone=e.timezone, name_override=e.name_override,
        call_permission=e.call_permission,
        forward_immediate_enabled=e.forward_immediate_enabled, forward_immediate_destination=e.forward_immediate_destination,
        forward_immediate_destination_type=e.forward_immediate_destination_type,
        forward_busy_enabled=e.forward_busy_enabled, forward_busy_destination=e.forward_busy_destination,
        forward_busy_destination_type=e.forward_busy_destination_type,
        forward_no_answer_enabled=e.forward_no_answer_enabled, forward_no_answer_destination=e.forward_no_answer_destination,
        forward_no_answer_destination_type=e.forward_no_answer_destination_type,
        forward_no_answer_delay_seconds=e.forward_no_answer_delay_seconds,
        forward_offline_enabled=e.forward_offline_enabled, forward_offline_destination=e.forward_offline_destination,
        forward_offline_destination_type=e.forward_offline_destination_type,
        dnd_enabled=e.dnd_enabled, dnd_locked=e.dnd_locked, auto_answer_enabled=e.auto_answer_enabled,
        max_concurrent_calls=e.max_concurrent_calls, distinctive_ring=e.distinctive_ring,
        pickup_group=e.pickup_group, paging_groups=e.paging_groups, can_intercept_calls=e.can_intercept_calls,
        intercom_warning_tone=e.intercom_warning_tone, intercom_mic_muted_on_answer=e.intercom_mic_muted_on_answer,
        paging_priority=e.paging_priority, paging_allow_send=e.paging_allow_send, paging_allow_receive=e.paging_allow_receive,
        paging_emergency=e.paging_emergency, multicast_address=e.multicast_address, multicast_port=e.multicast_port,
        forced_volume=e.forced_volume,
        ring_internal=e.ring_internal, ring_external=e.ring_external, ring_queue=e.ring_queue,
        silent_ring=e.silent_ring, caller_id_ring_rules=e.caller_id_ring_rules,
        groups=groups or [],
        allow_canada=e.allow_canada, allow_us=e.allow_us, allow_international=e.allow_international,
        allow_premium=e.allow_premium, blocked_countries=e.blocked_countries, blocked_prefixes=e.blocked_prefixes,
        has_ld_pin=bool(e.ld_pin), ld_monthly_limit=float(e.ld_monthly_limit) if e.ld_monthly_limit is not None else None,
        preferred_trunk_id=e.preferred_trunk_id,
        caller_id_internal_name=e.caller_id_internal_name, caller_id_internal_number=e.caller_id_internal_number,
        caller_id_external_name=e.caller_id_external_name, caller_id_external_number=e.caller_id_external_number,
        hide_caller_id=e.hide_caller_id,
    )


async def _groups_for(e: SIPExtension, db: AsyncSession) -> list[str]:
    """Groupes d'appartenance (IVR/queue/ring group) -- lecture seule, calcule a la volee,
    pas stocke (TASK-S018.3)."""
    from app.models.ivr import Queue, QueueMember, RingGroup
    groups: list[str] = []
    qresult = await db.execute(
        select(Queue.name).join(QueueMember, QueueMember.queue_id == Queue.id)
        .where(QueueMember.extension_username == e.username)
    )
    groups += [f"File d'attente : {name}" for name in qresult.scalars().all()]
    for name, members in (await db.execute(
        select(RingGroup.name, RingGroup.members).where(RingGroup.tenant_id == e.tenant_id)
    )).all():
        if e.username in [m.strip() for m in (members or "").split(",")]:
            groups.append(f"Groupe d'appel : {name}")
    return groups


def _snapshot(e: SIPExtension) -> dict:
    """Snapshot lisible d'une extension pour l'audit (sans mot de passe)."""
    return {
        "extension": e.extension,
        "name": e.name,
        "username": e.username,
        "voicemail_enabled": e.voicemail_enabled,
        "voicemail_email": e.voicemail_email,
        "caller_id_name": e.caller_id_name,
        "caller_id_number": e.caller_id_number,
        "record_calls": e.record_calls,
        "record_mode": e.record_mode,
        "record_internal_incoming": e.record_internal_incoming,
        "record_internal_outgoing": e.record_internal_outgoing,
        "record_external_incoming": e.record_external_incoming,
        "record_external_outgoing": e.record_external_outgoing,
        "max_contacts": e.max_contacts,
        "is_active": e.is_active,
        "codec_list": e.codec_list,
        "transport": e.transport,
        "schedule_id": str(e.schedule_id) if e.schedule_id else None,
        "site": e.site,
        "description": e.description,
        "display_language": e.display_language,
        "timezone": e.timezone,
        "name_override": e.name_override,
        "call_permission": e.call_permission,
        "forward_immediate_enabled": e.forward_immediate_enabled,
        "forward_immediate_destination": e.forward_immediate_destination,
        "forward_immediate_destination_type": e.forward_immediate_destination_type,
        "forward_busy_enabled": e.forward_busy_enabled,
        "forward_busy_destination": e.forward_busy_destination,
        "forward_busy_destination_type": e.forward_busy_destination_type,
        "forward_no_answer_enabled": e.forward_no_answer_enabled,
        "forward_no_answer_destination": e.forward_no_answer_destination,
        "forward_no_answer_destination_type": e.forward_no_answer_destination_type,
        "forward_no_answer_delay_seconds": e.forward_no_answer_delay_seconds,
        "forward_offline_enabled": e.forward_offline_enabled,
        "forward_offline_destination": e.forward_offline_destination,
        "forward_offline_destination_type": e.forward_offline_destination_type,
        "dnd_enabled": e.dnd_enabled,
        "dnd_locked": e.dnd_locked,
        "auto_answer_enabled": e.auto_answer_enabled,
        "max_concurrent_calls": e.max_concurrent_calls,
        "distinctive_ring": e.distinctive_ring,
        "pickup_group": e.pickup_group,
        "paging_groups": e.paging_groups,
        "can_intercept_calls": e.can_intercept_calls,
        "intercom_warning_tone": e.intercom_warning_tone,
        "intercom_mic_muted_on_answer": e.intercom_mic_muted_on_answer,
        "paging_priority": e.paging_priority,
        "paging_allow_send": e.paging_allow_send,
        "paging_allow_receive": e.paging_allow_receive,
        "paging_emergency": e.paging_emergency,
        "multicast_address": e.multicast_address,
        "multicast_port": e.multicast_port,
        "forced_volume": e.forced_volume,
        "ring_internal": e.ring_internal,
        "ring_external": e.ring_external,
        "ring_queue": e.ring_queue,
        "silent_ring": e.silent_ring,
        "caller_id_ring_rules": e.caller_id_ring_rules,
        "allow_canada": e.allow_canada,
        "allow_us": e.allow_us,
        "allow_international": e.allow_international,
        "allow_premium": e.allow_premium,
        "blocked_countries": e.blocked_countries,
        "blocked_prefixes": e.blocked_prefixes,
        "has_ld_pin": bool(e.ld_pin),
        "ld_monthly_limit": float(e.ld_monthly_limit) if e.ld_monthly_limit is not None else None,
        "preferred_trunk_id": str(e.preferred_trunk_id) if e.preferred_trunk_id else None,
        "caller_id_internal_name": e.caller_id_internal_name,
        "caller_id_internal_number": e.caller_id_internal_number,
        "caller_id_external_name": e.caller_id_external_name,
        "caller_id_external_number": e.caller_id_external_number,
        "hide_caller_id": e.hide_caller_id,
    }


@router.get("/tenant/{tenant_id}", response_model=list[ExtOut])
async def list_extensions(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(SIPExtension).where(SIPExtension.tenant_id == tenant_id).order_by(SIPExtension.extension))
    return [_out(e) for e in result.scalars().all()]


@router.get("/by-contact/{erpcrm_contact_id}", response_model=list[ExtOut])
async def get_extensions_by_contact(
    erpcrm_contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Appele par ERPCRM (proxy) pour afficher le poste SIP lie a un contact sur sa fiche.
    Authentifie par X-Api-Key (meme cle que /sync/company) — jamais par login utilisateur,
    puisque c'est ERPCRM (un serveur) qui appelle, pas un utilisateur SIPV.
    """
    result = await db.execute(select(SIPExtension).where(SIPExtension.erpcrm_contact_id == erpcrm_contact_id))
    return [_out(e) for e in result.scalars().all()]


@router.get("/{ext_id}", response_model=ExtOut)
async def get_extension(ext_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SIPExtension).where(SIPExtension.id == ext_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension introuvable")
    return _out(ext, await _groups_for(ext, db))


@router.post("/tenant/{tenant_id}", response_model=ExtOut, status_code=status.HTTP_201_CREATED)
async def create_extension(
    tenant_id: uuid.UUID,
    payload: ExtCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    username = f"{tenant.account_number}-{payload.extension}"
    existing = await db.execute(select(SIPExtension).where(SIPExtension.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Extension {payload.extension} déjà existante pour ce tenant")
    password = payload.password or secrets.token_urlsafe(12)
    ext = SIPExtension(
        tenant_id=tenant_id, username=username, password=encrypt(password),
        ld_pin=encrypt(payload.ld_pin) if payload.ld_pin else None,
        **payload.model_dump(exclude={"password", "ld_pin"}),
    )
    db.add(ext)
    change = PendingChange(
        tenant_id=tenant_id, change_type="add_extension", entity_type="extension",
        payload={"username": username, "extension": payload.extension, "name": payload.name, "password": password},
        created_by=user.email,
    )
    db.add(change)
    await log_audit(
        db, request=request, user=user,
        tenant_id=tenant_id, entity_type="extension", entity_id=str(ext.id),
        entity_label=f"Poste {payload.extension} — {payload.name}",
        action="create",
        old_data=None,
        new_data={
            "extension": payload.extension, "name": payload.name, "username": username,
            "voicemail_enabled": payload.voicemail_enabled, "voicemail_email": payload.voicemail_email,
            "caller_id_name": payload.caller_id_name, "caller_id_number": payload.caller_id_number,
            "record_calls": payload.record_calls, "max_contacts": payload.max_contacts,
            "password_set": True,
        },
    )
    await db.commit()
    await db.refresh(ext)

    erpcrm_contact_id = await _link_erpcrm_contact(ext)
    if erpcrm_contact_id:
        ext.erpcrm_contact_id = erpcrm_contact_id
        await db.commit()
        await db.refresh(ext)

    return _out(ext)


@router.put("/{ext_id}", response_model=ExtOut)
async def update_extension(
    ext_id: uuid.UUID,
    payload: ExtUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_or_service),
):
    result = await db.execute(select(SIPExtension).where(SIPExtension.id == ext_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension introuvable")

    old_data = _snapshot(ext)

    data = payload.model_dump(exclude_unset=True)
    password_changed = "password" in data
    new_password = data.pop("password", None)
    if new_password:
        ext.password = encrypt(new_password)
    if "ld_pin" in data:
        raw_pin = data.pop("ld_pin")
        ext.ld_pin = encrypt(raw_pin) if raw_pin else None
    for k, v in data.items():
        setattr(ext, k, v)
    ext.freeswitch_synced = False
    ext.updated_at = datetime.now(timezone.utc)

    new_data = _snapshot(ext)
    if password_changed:
        new_data["password_changed"] = True

    change = PendingChange(
        tenant_id=ext.tenant_id, change_type="update_extension", entity_type="extension",
        entity_id=str(ext_id),
        payload={k: v for k, v in data.items()},
        created_by=user.email if user else "erpcrm-proxy",
    )
    db.add(change)
    await log_audit(
        db, request=request, user=user,
        tenant_id=ext.tenant_id, entity_type="extension", entity_id=str(ext_id),
        entity_label=f"Poste {ext.extension} — {ext.name}",
        action="update",
        old_data=old_data,
        new_data=new_data,
    )
    await db.commit()
    await db.refresh(ext)
    return _out(ext, await _groups_for(ext, db))


class RegeneratePasswordOut(BaseModel):
    id: uuid.UUID
    password: str


class ConnectionInfoOut(BaseModel):
    id: uuid.UUID
    extension: str
    username: str
    password: str
    sip_server: str
    outbound_proxy: str
    port: int
    transport: str


@router.get("/{ext_id}/connection-info", response_model=ConnectionInfoOut)
async def get_connection_info(
    ext_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Infos de connexion completes (avec mot de passe en clair) pour configuration
    manuelle d'un telephone quand le provisioning automatique echoue (ex: reseau
    qui bloque le provisioning). Mot de passe stocke chiffre (Fernet) en base,
    dechiffre uniquement ici a la demande -- pas de log d'audit sur cette lecture,
    meme pattern que reveal-admin-password (provisioning.py). Authentifie par
    X-Api-Key : appele par ERPCRM (proxy), jamais directement par le frontend client,
    meme pattern que by-contact/{erpcrm_contact_id}.
    """
    result = await db.execute(select(SIPExtension).where(SIPExtension.id == ext_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension introuvable")
    tenant = await db.get(Tenant, ext.tenant_id)
    return ConnectionInfoOut(
        id=ext.id, extension=ext.extension, username=ext.username,
        password=decrypt(ext.password),
        sip_server=tenant.account_number if tenant else "",
        outbound_proxy=settings.SIPV_PUBLIC_IP,
        port=5061 if ext.transport == "tls" else 5060,
        transport=ext.transport,
    )


@router.post("/{ext_id}/regenerate-password", response_model=RegeneratePasswordOut)
async def regenerate_password(
    ext_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a new SIP password server-side (secrets.token_urlsafe, same as extension creation)."""
    result = await db.execute(select(SIPExtension).where(SIPExtension.id == ext_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension introuvable")

    old_data = _snapshot(ext)
    new_password = secrets.token_urlsafe(12)
    ext.password = encrypt(new_password)
    ext.freeswitch_synced = False
    ext.updated_at = datetime.now(timezone.utc)

    change = PendingChange(
        tenant_id=ext.tenant_id, change_type="update_extension", entity_type="extension",
        entity_id=str(ext_id), payload={"password_changed": True}, created_by=user.email,
    )
    db.add(change)
    await log_audit(
        db, request=request, user=user,
        tenant_id=ext.tenant_id, entity_type="extension", entity_id=str(ext_id),
        entity_label=f"Poste {ext.extension} — {ext.name}",
        action="update",
        old_data=old_data,
        new_data={**_snapshot(ext), "password_changed": True},
    )
    await db.commit()
    return RegeneratePasswordOut(id=ext.id, password=new_password)


@router.delete("/{ext_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_extension(
    ext_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SIPExtension).where(SIPExtension.id == ext_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension introuvable")

    # Snapshot de suppression : inclut le mot de passe (contrairement a _snapshot() utilise
    # pour create/update) pour permettre de recreer le poste a l'identique plus tard.
    old_data = {**_snapshot(ext), "password": decrypt(ext.password)}
    erpcrm_contact_id = ext.erpcrm_contact_id

    change = PendingChange(
        tenant_id=ext.tenant_id, change_type="remove_extension", entity_type="extension",
        entity_id=str(ext_id),
        payload={"username": ext.username, "extension": ext.extension},
        created_by=user.email,
    )
    db.add(change)
    await log_audit(
        db, request=request, user=user,
        tenant_id=ext.tenant_id, entity_type="extension", entity_id=str(ext_id),
        entity_label=f"Poste {ext.extension} — {ext.name}",
        action="delete",
        old_data=old_data,
        new_data=None,
    )
    await db.delete(ext)

    if erpcrm_contact_id:
        try:
            await erpcrm_client.update_contact(str(erpcrm_contact_id), sipv_sync=False)
        except httpx.HTTPError as e:
            logger.warning("Decochage sipv_sync ERPCRM echoue pour contact %s: %s", erpcrm_contact_id, e)
    await db.commit()
