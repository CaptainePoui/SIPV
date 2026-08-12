import logging
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.did_route_sync import sync_inbound_route_from_did
from app.core import erpcrm_client
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.sip import TenantDID
from app.models.dialplan import InboundRoute
from app.models.pending_change import PendingChange
from app.models.user import User

logger = logging.getLogger("dids")
router = APIRouter()

DESTINATION_TYPES = {
    "extension": "Extension",
    "ivr": "IVR",
    "queue": "File d'attente",
    "voicemail": "Messagerie",
    "hangup": "Raccrocher",
    "fax": "Fax virtuel",
    "conference": "Conférence",
    "transfer": "Transfert d'appel",
    "message": "Message enregistré",
}


class DIDOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    number: str
    label: str | None
    destination_type: str
    destination_type_label: str
    destination: str | None
    after_message_destination_type: str | None
    after_message_destination: str | None
    has_911: bool
    e911_address: str | None
    is_active: bool
    created_at: datetime

class DIDCreate(BaseModel):
    number: str
    label: str | None = None
    destination_type: str = "extension"
    destination: str | None = None
    after_message_destination_type: str | None = None
    after_message_destination: str | None = None
    has_911: bool = False
    e911_address: str | None = None

class DIDUpdate(BaseModel):
    label: str | None = None
    destination_type: str | None = None
    destination: str | None = None
    after_message_destination_type: str | None = None
    after_message_destination: str | None = None
    has_911: bool | None = None
    e911_address: str | None = None
    is_active: bool | None = None


def _out(d: TenantDID) -> DIDOut:
    return DIDOut(
        id=d.id, tenant_id=d.tenant_id, number=d.number, label=d.label,
        destination_type=d.destination_type,
        destination_type_label=DESTINATION_TYPES.get(d.destination_type, d.destination_type),
        destination=d.destination,
        after_message_destination_type=d.after_message_destination_type,
        after_message_destination=d.after_message_destination,
        has_911=d.has_911, e911_address=d.e911_address,
        is_active=d.is_active, created_at=d.created_at,
    )


@router.get("/tenant/{tenant_id}", response_model=list[DIDOut])
async def list_dids(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(TenantDID).where(TenantDID.tenant_id == tenant_id).order_by(TenantDID.number))
    return [_out(d) for d in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=DIDOut, status_code=status.HTTP_201_CREATED)
async def create_did(tenant_id: uuid.UUID, payload: DIDCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    existing = await db.execute(select(TenantDID).where(TenantDID.number == payload.number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"DID {payload.number} déjà assigné")
    if payload.destination_type not in DESTINATION_TYPES:
        raise HTTPException(status_code=400, detail="Type de destination invalide")
    d = TenantDID(tenant_id=tenant_id, **payload.model_dump())
    db.add(d)
    await db.flush()
    await sync_inbound_route_from_did(d, db)
    change = PendingChange(
        tenant_id=tenant_id, change_type="add_did", entity_type="did",
        payload={"number": payload.number, "destination_type": payload.destination_type, "destination": payload.destination},
        created_by=user.email,
    )
    db.add(change)
    await db.commit()
    await db.refresh(d)
    return _out(d)


@router.put("/{did_id}", response_model=DIDOut)
async def update_did(did_id: uuid.UUID, payload: DIDUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(TenantDID).where(TenantDID.id == did_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="DID introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    await sync_inbound_route_from_did(d, db)
    change = PendingChange(
        tenant_id=d.tenant_id, change_type="update_did", entity_type="did",
        entity_id=str(did_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email,
    )
    db.add(change)
    await db.commit()
    await db.refresh(d)
    return _out(d)


@router.delete("/{did_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_did(did_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service)):
    """user=None pour un appel de service ERPCRM (le DID est supprime cote
    ERPCRM d'abord, ce delete synchronise juste la copie SIPV, TASK-S010.5)."""
    result = await db.execute(select(TenantDID).where(TenantDID.id == did_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="DID introuvable")
    change = PendingChange(
        tenant_id=d.tenant_id, change_type="remove_did", entity_type="did",
        entity_id=str(did_id), payload={"number": d.number}, created_by=user.email if user else "erpcrm-sync",
    )
    db.add(change)
    route_result = await db.execute(select(InboundRoute).where(InboundRoute.did_id == did_id))
    route = route_result.scalar_one_or_none()
    if route is not None:
        await db.delete(route)
    tenant_id, did_uuid = d.tenant_id, d.id
    await db.delete(d)

    # TASK-021/S032 : notifie ERPCRM pour le prorata de facturation -- best-effort,
    # cet endpoint est LE chemin unique de suppression peu importe l'appelant
    # (ERPCRM ou admin SIPV natif), donc pas de risque de double notification.
    try:
        await erpcrm_client.send_billing_event(
            tenant_id=str(tenant_id), action="did_removed", service_type="did", service_ref=str(did_uuid),
        )
    except httpx.HTTPError as e:
        logger.warning("Notification facturation ERPCRM echouee (retrait DID) pour %s: %s", did_uuid, e)

    await db.commit()
