import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.recording import RecordingPolicy, CallRecording, StorageBackend
from app.models.user import User

router = APIRouter()


# ── Policy ────────────────────────────────────────────────────────────────────

class PolicyOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    record_inbound: bool
    record_outbound: bool
    record_internal: bool
    retention_days: int
    storage_backend: str
    storage_path: str | None
    is_active: bool

class PolicyUpsert(BaseModel):
    record_inbound: bool = False
    record_outbound: bool = False
    record_internal: bool = False
    retention_days: int = 90
    storage_backend: StorageBackend = StorageBackend.local
    storage_path: str | None = None
    storage_credentials: str | None = None
    is_active: bool = True


def _policy_out(p: RecordingPolicy) -> PolicyOut:
    return PolicyOut(id=p.id, tenant_id=p.tenant_id, record_inbound=p.record_inbound,
                     record_outbound=p.record_outbound, record_internal=p.record_internal,
                     retention_days=p.retention_days, storage_backend=p.storage_backend.value,
                     storage_path=p.storage_path, is_active=p.is_active)


@router.get("/policy/{tenant_id}", response_model=PolicyOut)
async def get_policy(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(RecordingPolicy).where(RecordingPolicy.tenant_id == tenant_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Aucune politique d'enregistrement pour ce tenant")
    return _policy_out(p)


@router.put("/policy/{tenant_id}", response_model=PolicyOut)
async def upsert_policy(tenant_id: uuid.UUID, payload: PolicyUpsert, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(RecordingPolicy).where(RecordingPolicy.tenant_id == tenant_id))
    p = result.scalar_one_or_none()
    if p:
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(p, k, v)
    else:
        p = RecordingPolicy(tenant_id=tenant_id, **payload.model_dump())
        db.add(p)
    await db.commit()
    await db.refresh(p)
    return _policy_out(p)


# ── Recordings ────────────────────────────────────────────────────────────────

class RecordingOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    cdr_id: uuid.UUID | None
    uniqueid: str | None
    filename: str
    storage_backend: str
    storage_path: str | None
    file_size: int | None
    duration: int | None
    format: str | None
    caller: str | None
    callee: str | None
    direction: str | None
    started_at: datetime | None
    expires_at: datetime | None
    is_deleted: bool

class RecordingCreate(BaseModel):
    cdr_id: uuid.UUID | None = None
    uniqueid: str | None = None
    filename: str
    storage_backend: str = "local"
    storage_path: str | None = None
    file_size: int | None = None
    duration: int | None = None
    format: str | None = None
    caller: str | None = None
    callee: str | None = None
    direction: str | None = None
    started_at: datetime | None = None
    retention_days: int | None = None  # override policy default


def _rec_out(r: CallRecording) -> RecordingOut:
    return RecordingOut(id=r.id, tenant_id=r.tenant_id, cdr_id=r.cdr_id, uniqueid=r.uniqueid,
                        filename=r.filename, storage_backend=r.storage_backend, storage_path=r.storage_path,
                        file_size=r.file_size, duration=r.duration, format=r.format,
                        caller=r.caller, callee=r.callee, direction=r.direction,
                        started_at=r.started_at, expires_at=r.expires_at, is_deleted=r.is_deleted)


@router.get("/tenant/{tenant_id}", response_model=list[RecordingOut])
async def list_recordings(
    tenant_id: uuid.UUID,
    direction: str | None = Query(None),
    include_deleted: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    filters = [CallRecording.tenant_id == tenant_id]
    if not include_deleted:
        filters.append(CallRecording.is_deleted == False)
    if direction:
        filters.append(CallRecording.direction == direction)
    result = await db.execute(
        select(CallRecording).where(and_(*filters))
        .order_by(CallRecording.started_at.desc()).limit(limit)
    )
    return [_rec_out(r) for r in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=RecordingOut, status_code=status.HTTP_201_CREATED)
async def create_recording(tenant_id: uuid.UUID, payload: RecordingCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    retention = payload.retention_days
    if retention is None:
        pol = await db.execute(select(RecordingPolicy).where(RecordingPolicy.tenant_id == tenant_id))
        policy = pol.scalar_one_or_none()
        retention = policy.retention_days if policy else 90

    expires_at = None
    if retention and retention > 0 and payload.started_at:
        expires_at = payload.started_at + timedelta(days=retention)

    data = payload.model_dump(exclude={"retention_days"})
    r = CallRecording(tenant_id=tenant_id, expires_at=expires_at, **data)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _rec_out(r)


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(recording_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(CallRecording).where(CallRecording.id == recording_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Enregistrement introuvable")
    r.is_deleted = True
    await db.commit()
