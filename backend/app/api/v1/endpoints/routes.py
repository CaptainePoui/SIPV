import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.dialplan import OutboundRoute, InboundRoute
from app.models.pending_change import PendingChange
from app.models.user import User

router = APIRouter()

DEST_TYPES = {"extension": "Extension", "ivr": "IVR", "queue": "File d'attente", "voicemail": "Messagerie", "hangup": "Raccrocher"}


# ── Outbound Routes ───────────────────────────────────────────────────────────

class OutboundRouteOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    dial_patterns: str
    trunk_id: uuid.UUID
    strip_digits: int
    prepend_digits: str | None
    caller_id_override: str | None
    priority: int
    is_active: bool
    created_at: datetime

class OutboundRouteCreate(BaseModel):
    name: str
    dial_patterns: str  # "NXXNXXXXXX,1NXXNXXXXXX"
    trunk_id: uuid.UUID
    strip_digits: int = 0
    prepend_digits: str | None = None
    caller_id_override: str | None = None
    priority: int = 10

class OutboundRouteUpdate(BaseModel):
    name: str | None = None
    dial_patterns: str | None = None
    trunk_id: uuid.UUID | None = None
    strip_digits: int | None = None
    prepend_digits: str | None = None
    caller_id_override: str | None = None
    priority: int | None = None
    is_active: bool | None = None


def _out_route(r: OutboundRoute) -> OutboundRouteOut:
    return OutboundRouteOut(
        id=r.id, tenant_id=r.tenant_id, name=r.name, dial_patterns=r.dial_patterns,
        trunk_id=r.trunk_id, strip_digits=r.strip_digits, prepend_digits=r.prepend_digits,
        caller_id_override=r.caller_id_override, priority=r.priority, is_active=r.is_active, created_at=r.created_at,
    )


@router.get("/outbound/tenant/{tenant_id}", response_model=list[OutboundRouteOut])
async def list_outbound(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(OutboundRoute).where(OutboundRoute.tenant_id == tenant_id).order_by(OutboundRoute.priority))
    return [_out_route(r) for r in result.scalars().all()]


@router.post("/outbound/tenant/{tenant_id}", response_model=OutboundRouteOut, status_code=status.HTTP_201_CREATED)
async def create_outbound(tenant_id: uuid.UUID, payload: OutboundRouteCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    r = OutboundRoute(tenant_id=tenant_id, **payload.model_dump())
    db.add(r)
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_outbound_route", entity_type="dialplan",
                         payload={"name": payload.name, "patterns": payload.dial_patterns}, created_by=user.email))
    await db.commit()
    await db.refresh(r)
    return _out_route(r)


@router.put("/outbound/{route_id}", response_model=OutboundRouteOut)
async def update_outbound(route_id: uuid.UUID, payload: OutboundRouteUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(OutboundRoute).where(OutboundRoute.id == route_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Route sortante introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    r.asterisk_synced = False
    db.add(PendingChange(tenant_id=r.tenant_id, change_type="update_outbound_route", entity_type="dialplan",
                         entity_id=str(route_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email))
    await db.commit()
    await db.refresh(r)
    return _out_route(r)


@router.delete("/outbound/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outbound(route_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(OutboundRoute).where(OutboundRoute.id == route_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Route sortante introuvable")
    db.add(PendingChange(tenant_id=r.tenant_id, change_type="remove_outbound_route", entity_type="dialplan",
                         entity_id=str(route_id), payload={"name": r.name}, created_by=user.email))
    await db.delete(r)
    await db.commit()


# ── Inbound Routes ────────────────────────────────────────────────────────────

class InboundRouteOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    did_id: uuid.UUID | None
    did_number: str
    name: str
    destination_type: str
    destination_type_label: str
    destination: str
    is_active: bool
    created_at: datetime

class InboundRouteCreate(BaseModel):
    did_id: uuid.UUID | None = None
    did_number: str
    name: str
    destination_type: str = "extension"
    destination: str

class InboundRouteUpdate(BaseModel):
    name: str | None = None
    destination_type: str | None = None
    destination: str | None = None
    is_active: bool | None = None


def _in_route(r: InboundRoute) -> InboundRouteOut:
    return InboundRouteOut(
        id=r.id, tenant_id=r.tenant_id, did_id=r.did_id, did_number=r.did_number, name=r.name,
        destination_type=r.destination_type, destination_type_label=DEST_TYPES.get(r.destination_type, r.destination_type),
        destination=r.destination, is_active=r.is_active, created_at=r.created_at,
    )


@router.get("/inbound/tenant/{tenant_id}", response_model=list[InboundRouteOut])
async def list_inbound(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(InboundRoute).where(InboundRoute.tenant_id == tenant_id).order_by(InboundRoute.did_number))
    return [_in_route(r) for r in result.scalars().all()]


@router.post("/inbound/tenant/{tenant_id}", response_model=InboundRouteOut, status_code=status.HTTP_201_CREATED)
async def create_inbound(tenant_id: uuid.UUID, payload: InboundRouteCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.destination_type not in DEST_TYPES:
        raise HTTPException(status_code=400, detail="Type destination invalide")
    r = InboundRoute(tenant_id=tenant_id, **payload.model_dump())
    db.add(r)
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_inbound_route", entity_type="dialplan",
                         payload={"did": payload.did_number, "dest": payload.destination}, created_by=user.email))
    await db.commit()
    await db.refresh(r)
    return _in_route(r)


@router.put("/inbound/{route_id}", response_model=InboundRouteOut)
async def update_inbound(route_id: uuid.UUID, payload: InboundRouteUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(InboundRoute).where(InboundRoute.id == route_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Route entrante introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    r.asterisk_synced = False
    db.add(PendingChange(tenant_id=r.tenant_id, change_type="update_inbound_route", entity_type="dialplan",
                         entity_id=str(route_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email))
    await db.commit()
    await db.refresh(r)
    return _in_route(r)


@router.delete("/inbound/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inbound(route_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(InboundRoute).where(InboundRoute.id == route_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Route entrante introuvable")
    db.add(PendingChange(tenant_id=r.tenant_id, change_type="remove_inbound_route", entity_type="dialplan",
                         entity_id=str(route_id), payload={"did": r.did_number}, created_by=user.email))
    await db.delete(r)
    await db.commit()
