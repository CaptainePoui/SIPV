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
from app.api.v1.endpoints.auth import get_current_user
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
    max_contacts: int
    is_active: bool
    codec: str | None
    schedule_id: uuid.UUID | None
    erpcrm_contact_id: uuid.UUID | None
    freeswitch_synced: bool
    created_at: datetime

class ExtCreate(BaseModel):
    extension: str
    name: str
    voicemail_enabled: bool = True
    voicemail_email: str | None = None
    caller_id_name: str | None = None
    caller_id_number: str | None = None
    record_calls: bool = False
    max_contacts: int = 3
    codec: str | None = None
    schedule_id: uuid.UUID | None = None
    password: str | None = None  # auto-generated if not provided

class ExtUpdate(BaseModel):
    name: str | None = None
    voicemail_enabled: bool | None = None
    voicemail_email: str | None = None
    caller_id_name: str | None = None
    caller_id_number: str | None = None
    record_calls: bool | None = None
    max_contacts: int | None = None
    is_active: bool | None = None
    codec: str | None = None
    schedule_id: uuid.UUID | None = None
    password: str | None = None


def _out(e: SIPExtension) -> ExtOut:
    return ExtOut(
        id=e.id, tenant_id=e.tenant_id, extension=e.extension, name=e.name,
        username=e.username, voicemail_enabled=e.voicemail_enabled, voicemail_email=e.voicemail_email,
        caller_id_name=e.caller_id_name, caller_id_number=e.caller_id_number,
        record_calls=e.record_calls, max_contacts=e.max_contacts,
        is_active=e.is_active, codec=e.codec, schedule_id=e.schedule_id,
        erpcrm_contact_id=e.erpcrm_contact_id,
        freeswitch_synced=e.freeswitch_synced, created_at=e.created_at,
    )


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
        "max_contacts": e.max_contacts,
        "is_active": e.is_active,
        "codec": e.codec,
        "schedule_id": str(e.schedule_id) if e.schedule_id else None,
    }


@router.get("/tenant/{tenant_id}", response_model=list[ExtOut])
async def list_extensions(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SIPExtension).where(SIPExtension.tenant_id == tenant_id).order_by(SIPExtension.extension))
    return [_out(e) for e in result.scalars().all()]


@router.get("/{ext_id}", response_model=ExtOut)
async def get_extension(ext_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SIPExtension).where(SIPExtension.id == ext_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Extension introuvable")
    return _out(ext)


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
        tenant_id=tenant_id, extension=payload.extension, name=payload.name,
        username=username, password=password,
        voicemail_enabled=payload.voicemail_enabled, voicemail_email=payload.voicemail_email,
        caller_id_name=payload.caller_id_name, caller_id_number=payload.caller_id_number,
        record_calls=payload.record_calls, max_contacts=payload.max_contacts,
        codec=payload.codec, schedule_id=payload.schedule_id,
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
    user: User = Depends(get_current_user),
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
        ext.password = new_password
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
        created_by=user.email,
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
    return _out(ext)


class RegeneratePasswordOut(BaseModel):
    id: uuid.UUID
    password: str


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
    ext.password = new_password
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
    old_data = {**_snapshot(ext), "password": ext.password}
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
