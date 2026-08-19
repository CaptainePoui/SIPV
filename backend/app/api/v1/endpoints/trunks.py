import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.crypto import encrypt, decrypt
from app.core.esl import get_esl, ESLClient
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.sip import SIPTrunk
from app.models.tenant import Tenant
from app.models.dialplan import OutboundRoute
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
    has_password: bool = False  # jamais le mot de passe en clair dans la liste/fiche
    from_domain: str | None
    caller_id: str | None
    failover_trunk_id: uuid.UUID | None
    is_active: bool
    freeswitch_synced: bool
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
        host=t.host, username=t.username, has_password=bool(t.password),
        from_domain=t.from_domain, caller_id=t.caller_id,
        failover_trunk_id=t.failover_trunk_id, is_active=t.is_active,
        freeswitch_synced=t.freeswitch_synced, created_at=t.created_at,
    )


@router.get("/tenant/{tenant_id}", response_model=list[TrunkOut])
async def list_trunks(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.tenant_id == tenant_id).order_by(SIPTrunk.name))
    return [_out(t) for t in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=TrunkOut, status_code=status.HTTP_201_CREATED)
async def create_trunk(tenant_id: uuid.UUID, payload: TrunkCreate, db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service)):
    trunk_name = f"trunk-{payload.name.lower().replace(' ', '_')}"
    data = payload.model_dump()
    if data.get("password"):
        data["password"] = encrypt(data["password"])
    t = SIPTrunk(tenant_id=tenant_id, **data)
    db.add(t)
    change = PendingChange(
        tenant_id=tenant_id, change_type="add_trunk", entity_type="trunk",
        payload={"name": trunk_name, "host": payload.host, "username": payload.username},
        created_by=user.email if user else "erpcrm-proxy",
    )
    db.add(change)
    await db.commit()
    await db.refresh(t)
    return _out(t)


@router.put("/{trunk_id}", response_model=TrunkOut)
async def update_trunk(trunk_id: uuid.UUID, payload: TrunkUpdate, db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.id == trunk_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Trunk introuvable")
    data = payload.model_dump(exclude_unset=True)
    if data.get("password"):
        data["password"] = encrypt(data["password"])
    for k, v in data.items():
        setattr(t, k, v)
    t.freeswitch_synced = False
    change = PendingChange(
        tenant_id=t.tenant_id, change_type="update_trunk", entity_type="trunk",
        entity_id=str(trunk_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email if user else "erpcrm-proxy",
    )
    db.add(change)
    await db.commit()
    await db.refresh(t)
    return _out(t)


@router.delete("/{trunk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trunk(trunk_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.id == trunk_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Trunk introuvable")
    change = PendingChange(
        tenant_id=t.tenant_id, change_type="remove_trunk", entity_type="trunk",
        entity_id=str(trunk_id), payload={"name": t.name, "host": t.host}, created_by=user.email if user else "erpcrm-proxy",
    )
    db.add(change)
    await db.delete(t)
    await db.commit()



# ── Fiche trunk unifiee (TASK-S018.2) ────────────────────────────────────────

class TrunkStatusOut(BaseModel):
    gateway_name: str
    state: str | None = None      # ex: REGED, NOREG, FAILED, TRYING
    status: str | None = None     # ex: UP, DOWN
    configured: bool              # False si le gateway n'existe pas encore sur FreeSWITCH
                                   # (fichier gateway = ecrit a la main sur le serveur,
                                   # pas genere depuis cette table -- voir TASK-023.27)
    error: str | None = None


@router.get("/{trunk_id}/status", response_model=TrunkStatusOut)
async def trunk_status(trunk_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """
    Statut live du gateway FreeSWITCH correspondant (sofia status gateway).
    Convention de nom deja etablie (xml_curl.py, TASK-023.27) :
    {tenant.account_number}-gw-{8 premiers caracteres du trunk_id}.
    Le fichier gateway lui-meme reste ecrit a la main sur le serveur (pas de
    generation dynamique depuis SIPTrunk) -- ce endpoint lit l'etat REEL du
    gateway s'il existe, mais ne le cree pas. "configured: false" = trunk
    enregistre dans SIPV mais jamais deploye sur FreeSWITCH.
    """
    result = await db.execute(select(SIPTrunk).where(SIPTrunk.id == trunk_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Trunk introuvable")
    tenant = await db.get(Tenant, t.tenant_id)
    gw_name = f"{tenant.account_number}-gw-{str(trunk_id)[:8]}"
    try:
        esl: ESLClient = await get_esl()
        raw = await esl.api(f"sofia status gateway {gw_name}")
    except Exception as exc:
        return TrunkStatusOut(gateway_name=gw_name, configured=False, error=f"ESL error: {exc}")
    if "invalid gateway" in raw.lower():
        return TrunkStatusOut(gateway_name=gw_name, configured=False, error="Gateway non deploye sur FreeSWITCH")
    state_m = re.search(r"^State\s+(\S+)", raw, re.MULTILINE)
    status_m = re.search(r"^Status\s+(\S+)", raw, re.MULTILINE)
    return TrunkStatusOut(
        gateway_name=gw_name, configured=True,
        state=state_m.group(1) if state_m else None,
        status=status_m.group(1) if status_m else None,
    )


class TrunkRouteOut(BaseModel):
    id: uuid.UUID
    name: str
    dial_patterns: str
    priority: int
    is_active: bool


@router.get("/{trunk_id}/routes", response_model=list[TrunkRouteOut])
async def trunk_routes(trunk_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Routes sortantes (OutboundRoute) qui utilisent ce trunk -- reellement lu
    par le dialplan dynamique (xml_curl.py), contrairement au gateway lui-meme."""
    result = await db.execute(
        select(OutboundRoute).where(OutboundRoute.trunk_id == trunk_id).order_by(OutboundRoute.priority)
    )
    return [
        TrunkRouteOut(id=r.id, name=r.name, dial_patterns=r.dial_patterns, priority=r.priority, is_active=r.is_active)
        for r in result.scalars().all()
    ]
