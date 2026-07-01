import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.sip import SIPTrunk
from app.models.pending_change import PendingChange
from app.models.user import User

router = APIRouter()

CALLER_ID_RESTRICTIONS = {
    "none": "Aucune restriction",
    "local_only": "Numéros locaux uniquement",
    "tenant_dids": "DIDs du tenant uniquement",
}


class TrunkOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    carrier_name: str
    host: str
    username: str | None
    from_domain: str | None
    caller_id: str | None
    failover_trunk_id: uuid.UUID | None
    is_active: bool
    asterisk_synced: bool
    created_at: datetime

class TrunkCreate(BaseModel):
    name: str
    carrier_name: str
    host: str
    username: str | None = None
    password: str | None = None
    from_domain: str | None = None
    caller_id: str | None = None
    failover_trunk_id: uuid.UUID | None = None

class TrunkUpdate(BaseModel):
    name: str | None = None
    carrier_name: str | None = None
    host: str | None = None
    username: str | None = None
    password: str | None = None
    from_domain: str | None = None
    caller_id: str | None = None
    failover_trunk_id: uuid.UUID | None = None
    is_active: bool | None = None


def _out(t: SIPTrunk) -> TrunkOut:
    return TrunkOut(
        id=t.id, tenant_id=t.tenant_id, name=t.name, carrier_name=t.carrier_name,
        host=t.host, username=t.username, from_domain=t.from_domain, caller_id=t.caller_id,
        failover_trunk_id=t.failover_trunk_id, is_active=t.is_active,
        asterisk_synced=t.asterisk_synced, created_at=t.created_at,
    )


@router.get("/tenant/{tenant_id}", response_model=list[TrunkOut])
async def list_trunks(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.tenant_id == tenant_id).order_by(SIPTrunk.name))
    return [_out(t) for t in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=TrunkOut, status_code=status.HTTP_201_CREATED)
async def create_trunk(tenant_id: uuid.UUID, payload: TrunkCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    trunk_name = f"trunk-{payload.name.lower().replace(' ', '_')}"
    t = SIPTrunk(tenant_id=tenant_id, **payload.model_dump())
    db.add(t)
    change = PendingChange(
        tenant_id=tenant_id, change_type="add_trunk", entity_type="trunk",
        payload={"name": trunk_name, "host": payload.host, "username": payload.username},
        created_by=user.email,
    )
    db.add(change)
    await db.commit()
    await db.refresh(t)
    return _out(t)


@router.put("/{trunk_id}", response_model=TrunkOut)
async def update_trunk(trunk_id: uuid.UUID, payload: TrunkUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.id == trunk_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Trunk introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    t.asterisk_synced = False
    change = PendingChange(
        tenant_id=t.tenant_id, change_type="update_trunk", entity_type="trunk",
        entity_id=str(trunk_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email,
    )
    db.add(change)
    await db.commit()
    await db.refresh(t)
    return _out(t)


@router.delete("/{trunk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trunk(trunk_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.id == trunk_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Trunk introuvable")
    change = PendingChange(
        tenant_id=t.tenant_id, change_type="remove_trunk", entity_type="trunk",
        entity_id=str(trunk_id), payload={"name": t.name, "host": t.host}, created_by=user.email,
    )
    db.add(change)
    await db.delete(t)
    await db.commit()
