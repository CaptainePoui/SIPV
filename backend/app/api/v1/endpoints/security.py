import uuid
import ipaddress
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.security import SecurityEvent, ACLRule, FraudRule, BlockedIP
from app.models.user import User

router = APIRouter()


# ── Security Events ───────────────────────────────────────────────────────────

class EventOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    event_type: str
    severity: str
    source_ip: str | None
    username: str | None
    description: str | None
    resolved: bool
    created_at: datetime

class EventCreate(BaseModel):
    tenant_id: uuid.UUID | None = None
    event_type: str
    severity: str = "info"
    source_ip: str | None = None
    username: str | None = None
    description: str | None = None


@router.get("/events", response_model=list[EventOut])
async def list_events(
    tenant_id: uuid.UUID | None = Query(None),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    resolved: bool | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    filters = []
    if tenant_id:
        filters.append(SecurityEvent.tenant_id == tenant_id)
    if event_type:
        filters.append(SecurityEvent.event_type == event_type)
    if severity:
        filters.append(SecurityEvent.severity == severity)
    if resolved is not None:
        filters.append(SecurityEvent.resolved == resolved)
    q = select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
    if filters:
        q = q.where(and_(*filters))
    result = await db.execute(q)
    return [EventOut(id=e.id, tenant_id=e.tenant_id, event_type=e.event_type, severity=e.severity,
                     source_ip=e.source_ip, username=e.username, description=e.description,
                     resolved=e.resolved, created_at=e.created_at)
            for e in result.scalars().all()]


@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    e = SecurityEvent(**payload.model_dump())
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return EventOut(id=e.id, tenant_id=e.tenant_id, event_type=e.event_type, severity=e.severity,
                    source_ip=e.source_ip, username=e.username, description=e.description,
                    resolved=e.resolved, created_at=e.created_at)


@router.put("/events/{event_id}/resolve", response_model=EventOut)
async def resolve_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SecurityEvent).where(SecurityEvent.id == event_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Événement introuvable")
    e.resolved = True
    await db.commit()
    await db.refresh(e)
    return EventOut(id=e.id, tenant_id=e.tenant_id, event_type=e.event_type, severity=e.severity,
                    source_ip=e.source_ip, username=e.username, description=e.description,
                    resolved=e.resolved, created_at=e.created_at)


# ── ACL Rules ─────────────────────────────────────────────────────────────────

class ACLOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    cidr: str
    action: str
    description: str | None
    priority: int
    is_active: bool

class ACLCreate(BaseModel):
    tenant_id: uuid.UUID | None = None
    cidr: str
    action: str  # allow / deny
    description: str | None = None
    priority: int = 100


@router.get("/acl", response_model=list[ACLOut])
async def list_acl(tenant_id: uuid.UUID | None = Query(None), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(ACLRule).where(ACLRule.is_active == True).order_by(ACLRule.priority, ACLRule.action)
    if tenant_id:
        q = q.where(ACLRule.tenant_id == tenant_id)
    result = await db.execute(q)
    return [ACLOut(id=r.id, tenant_id=r.tenant_id, cidr=r.cidr, action=r.action,
                   description=r.description, priority=r.priority, is_active=r.is_active)
            for r in result.scalars().all()]


@router.post("/acl", response_model=ACLOut, status_code=status.HTTP_201_CREATED)
async def create_acl(payload: ACLCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        ipaddress.ip_network(payload.cidr, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="CIDR invalide")
    if payload.action not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="Action doit être 'allow' ou 'deny'")
    r = ACLRule(**payload.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return ACLOut(id=r.id, tenant_id=r.tenant_id, cidr=r.cidr, action=r.action,
                  description=r.description, priority=r.priority, is_active=r.is_active)


@router.delete("/acl/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acl(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ACLRule).where(ACLRule.id == rule_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Règle ACL introuvable")
    await db.delete(r)
    await db.commit()


# ── Fraud Rules ───────────────────────────────────────────────────────────────

class FraudOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    max_calls_per_hour: int | None
    max_concurrent_calls: int | None
    max_international_calls_per_day: int | None
    block_international: bool
    block_premium: bool
    alert_email: str | None
    auto_block_on_alert: bool
    is_active: bool

class FraudUpsert(BaseModel):
    max_calls_per_hour: int | None = None
    max_concurrent_calls: int | None = None
    max_international_calls_per_day: int | None = None
    block_international: bool = False
    block_premium: bool = True
    alert_email: str | None = None
    auto_block_on_alert: bool = False
    is_active: bool = True


def _fraud_out(f: FraudRule) -> FraudOut:
    return FraudOut(id=f.id, tenant_id=f.tenant_id, max_calls_per_hour=f.max_calls_per_hour,
                    max_concurrent_calls=f.max_concurrent_calls,
                    max_international_calls_per_day=f.max_international_calls_per_day,
                    block_international=f.block_international, block_premium=f.block_premium,
                    alert_email=f.alert_email, auto_block_on_alert=f.auto_block_on_alert, is_active=f.is_active)


@router.get("/fraud/{tenant_id}", response_model=FraudOut)
async def get_fraud(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(FraudRule).where(FraudRule.tenant_id == tenant_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Aucune règle fraude pour ce tenant")
    return _fraud_out(f)


@router.put("/fraud/{tenant_id}", response_model=FraudOut)
async def upsert_fraud(tenant_id: uuid.UUID, payload: FraudUpsert, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(FraudRule).where(FraudRule.tenant_id == tenant_id))
    f = result.scalar_one_or_none()
    if f:
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(f, k, v)
    else:
        f = FraudRule(tenant_id=tenant_id, **payload.model_dump())
        db.add(f)
    await db.commit()
    await db.refresh(f)
    return _fraud_out(f)


# ── Blocked IPs ───────────────────────────────────────────────────────────────

class BlockedIPOut(BaseModel):
    id: uuid.UUID
    ip_address: str
    reason: str | None
    block_count: int
    expires_at: datetime | None
    created_at: datetime

class BlockIPCreate(BaseModel):
    ip_address: str
    reason: str | None = None
    expires_hours: int | None = 24  # None = permanent


@router.get("/blocked-ips", response_model=list[BlockedIPOut])
async def list_blocked(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(BlockedIP).order_by(BlockedIP.created_at.desc()))
    return [BlockedIPOut(id=b.id, ip_address=b.ip_address, reason=b.reason, block_count=b.block_count,
                         expires_at=b.expires_at, created_at=b.created_at)
            for b in result.scalars().all()]


@router.post("/blocked-ips", response_model=BlockedIPOut, status_code=status.HTTP_201_CREATED)
async def block_ip(payload: BlockIPCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_hours) if payload.expires_hours else None
    existing = await db.execute(select(BlockedIP).where(BlockedIP.ip_address == payload.ip_address))
    b = existing.scalar_one_or_none()
    if b:
        b.block_count += 1
        b.reason = payload.reason or b.reason
        b.expires_at = expires_at
    else:
        b = BlockedIP(ip_address=payload.ip_address, reason=payload.reason, expires_at=expires_at)
        db.add(b)
    await db.commit()
    await db.refresh(b)
    return BlockedIPOut(id=b.id, ip_address=b.ip_address, reason=b.reason, block_count=b.block_count,
                        expires_at=b.expires_at, created_at=b.created_at)


@router.delete("/blocked-ips/{ip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_ip(ip_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(BlockedIP).where(BlockedIP.id == ip_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="IP bloquée introuvable")
    await db.delete(b)
    await db.commit()
