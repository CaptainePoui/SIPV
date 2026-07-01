import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.fax import FaxLine, FaxJob, FaxDirection, FaxStatus
from app.models.user import User

router = APIRouter()


# ── Fax Lines ─────────────────────────────────────────────────────────────────

class FaxLineOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    did_id: uuid.UUID | None
    fax_number: str
    label: str | None
    delivery_email: str | None
    use_t38: bool
    ata_ip: str | None
    ata_model: str | None
    is_active: bool

class FaxLineCreate(BaseModel):
    did_id: uuid.UUID | None = None
    fax_number: str
    label: str | None = None
    delivery_email: str | None = None
    use_t38: bool = True
    ata_ip: str | None = None
    ata_model: str | None = None

class FaxLineUpdate(BaseModel):
    label: str | None = None
    delivery_email: str | None = None
    use_t38: bool | None = None
    ata_ip: str | None = None
    ata_model: str | None = None
    is_active: bool | None = None


def _line_out(f: FaxLine) -> FaxLineOut:
    return FaxLineOut(id=f.id, tenant_id=f.tenant_id, did_id=f.did_id, fax_number=f.fax_number,
                      label=f.label, delivery_email=f.delivery_email, use_t38=f.use_t38,
                      ata_ip=f.ata_ip, ata_model=f.ata_model, is_active=f.is_active)


@router.get("/lines/tenant/{tenant_id}", response_model=list[FaxLineOut])
async def list_fax_lines(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(FaxLine).where(FaxLine.tenant_id == tenant_id).order_by(FaxLine.fax_number))
    return [_line_out(f) for f in result.scalars().all()]


@router.post("/lines/tenant/{tenant_id}", response_model=FaxLineOut, status_code=status.HTTP_201_CREATED)
async def create_fax_line(tenant_id: uuid.UUID, payload: FaxLineCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    f = FaxLine(tenant_id=tenant_id, **payload.model_dump())
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return _line_out(f)


@router.put("/lines/{line_id}", response_model=FaxLineOut)
async def update_fax_line(line_id: uuid.UUID, payload: FaxLineUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(FaxLine).where(FaxLine.id == line_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Ligne fax introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    await db.commit()
    await db.refresh(f)
    return _line_out(f)


@router.delete("/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fax_line(line_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(FaxLine).where(FaxLine.id == line_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Ligne fax introuvable")
    await db.delete(f)
    await db.commit()


# ── Fax Jobs ──────────────────────────────────────────────────────────────────

class FaxJobOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    fax_line_id: uuid.UUID | None
    direction: str
    status: str
    remote_number: str | None
    pages: int | None
    file_path: str | None
    delivery_email: str | None
    email_sent: bool
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

class FaxJobCreate(BaseModel):
    fax_line_id: uuid.UUID | None = None
    direction: FaxDirection
    remote_number: str | None = None
    pages: int | None = None
    file_path: str | None = None
    delivery_email: str | None = None

class FaxJobStatusUpdate(BaseModel):
    status: FaxStatus
    pages: int | None = None
    file_path: str | None = None
    error_message: str | None = None
    email_sent: bool | None = None


def _job_out(j: FaxJob) -> FaxJobOut:
    return FaxJobOut(id=j.id, tenant_id=j.tenant_id, fax_line_id=j.fax_line_id,
                     direction=j.direction.value, status=j.status.value, remote_number=j.remote_number,
                     pages=j.pages, file_path=j.file_path, delivery_email=j.delivery_email,
                     email_sent=j.email_sent, error_message=j.error_message,
                     started_at=j.started_at, completed_at=j.completed_at, created_at=j.created_at)


@router.get("/jobs/tenant/{tenant_id}", response_model=list[FaxJobOut])
async def list_fax_jobs(tenant_id: uuid.UUID, limit: int = 100, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(FaxJob).where(FaxJob.tenant_id == tenant_id)
        .order_by(FaxJob.created_at.desc()).limit(limit)
    )
    return [_job_out(j) for j in result.scalars().all()]


@router.post("/jobs/tenant/{tenant_id}", response_model=FaxJobOut, status_code=status.HTTP_201_CREATED)
async def create_fax_job(tenant_id: uuid.UUID, payload: FaxJobCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    j = FaxJob(tenant_id=tenant_id, started_at=datetime.now(timezone.utc), **payload.model_dump())
    db.add(j)
    await db.commit()
    await db.refresh(j)
    return _job_out(j)


@router.put("/jobs/{job_id}/status", response_model=FaxJobOut)
async def update_fax_status(job_id: uuid.UUID, payload: FaxJobStatusUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(FaxJob).where(FaxJob.id == job_id))
    j = result.scalar_one_or_none()
    if not j:
        raise HTTPException(status_code=404, detail="Fax job introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(j, k, v)
    if payload.status in (FaxStatus.delivered, FaxStatus.failed):
        j.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(j)
    return _job_out(j)
