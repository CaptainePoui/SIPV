import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.core.database import get_db
from app.core.crypto import encrypt
from app.api.v1.endpoints.auth import get_current_user
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter()


class TenantOut(BaseModel):
    id: uuid.UUID
    account_number: str
    company_name: str
    erpcrm_company_id: str | None
    is_active: bool
    context_prefix: str
    max_extensions: int
    max_trunks: int
    notes: str | None
    created_at: datetime
    extension_count: int = 0
    trunk_count: int = 0
    did_count: int = 0
    voicemail_delete_after_email: bool | None = None  # null = herite du reglage global (TASK-S008.2)
    # --- TASK-S018.5 : defauts compagnie du plan d'appel ---
    default_allow_canada: bool = True
    default_allow_us: bool = True
    default_allow_international: bool = False
    default_allow_premium: bool = False
    default_blocked_countries: str | None = None
    default_blocked_prefixes: str | None = None
    has_default_ld_pin: bool = False  # jamais le NIP en clair dans la liste/fiche compagnie
    default_ld_monthly_limit: float | None = None

class TenantCreate(BaseModel):
    account_number: str
    company_name: str
    erpcrm_company_id: str | None = None
    max_extensions: int = 10
    max_trunks: int = 2
    notes: str | None = None

class TenantUpdate(BaseModel):
    company_name: str | None = None
    erpcrm_company_id: str | None = None
    is_active: bool | None = None
    max_extensions: int | None = None
    max_trunks: int | None = None
    notes: str | None = None
    voicemail_delete_after_email: bool | None = None
    default_allow_canada: bool | None = None
    default_allow_us: bool | None = None
    default_allow_international: bool | None = None
    default_allow_premium: bool | None = None
    default_blocked_countries: str | None = None
    default_blocked_prefixes: str | None = None
    default_ld_pin: str | None = None  # en clair a l'entree, chiffre avant stockage
    default_ld_monthly_limit: float | None = None


def _tenant_out(t: Tenant) -> TenantOut:
    return TenantOut(
        id=t.id, account_number=t.account_number, company_name=t.company_name,
        erpcrm_company_id=t.erpcrm_company_id, is_active=t.is_active,
        context_prefix=t.context_prefix, max_extensions=t.max_extensions, max_trunks=t.max_trunks,
        notes=t.notes, created_at=t.created_at,
        extension_count=len(t.extensions) if t.extensions else 0,
        trunk_count=len(t.trunks) if t.trunks else 0,
        did_count=len(t.dids) if t.dids else 0,
        voicemail_delete_after_email=t.voicemail_delete_after_email,
        default_allow_canada=t.default_allow_canada, default_allow_us=t.default_allow_us,
        default_allow_international=t.default_allow_international, default_allow_premium=t.default_allow_premium,
        default_blocked_countries=t.default_blocked_countries, default_blocked_prefixes=t.default_blocked_prefixes,
        has_default_ld_pin=bool(t.default_ld_pin), default_ld_monthly_limit=float(t.default_ld_monthly_limit) if t.default_ld_monthly_limit is not None else None,
    )


@router.get("/", response_model=list[TenantOut])
async def list_tenants(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.extensions), selectinload(Tenant.trunks), selectinload(Tenant.dids))
        .order_by(Tenant.company_name)
    )
    return [_tenant_out(t) for t in result.scalars().all()]


@router.post("/", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    existing = await db.execute(select(Tenant).where(Tenant.account_number == payload.account_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Numéro de compte déjà utilisé")
    context_prefix = f"t-{payload.account_number.lower().replace(' ', '_').replace('-', '_')}"
    t = Tenant(context_prefix=context_prefix, **payload.model_dump())
    db.add(t)
    await db.flush()
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.extensions), selectinload(Tenant.trunks), selectinload(Tenant.dids))
        .where(Tenant.id == t.id)
    )
    t = result.scalar_one()
    await db.commit()
    return _tenant_out(t)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.extensions), selectinload(Tenant.trunks), selectinload(Tenant.dids))
        .where(Tenant.id == tenant_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    return _tenant_out(t)


@router.put("/{tenant_id}", response_model=TenantOut)
async def update_tenant(tenant_id: uuid.UUID, payload: TenantUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.extensions), selectinload(Tenant.trunks), selectinload(Tenant.dids))
        .where(Tenant.id == tenant_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "default_ld_pin" in data:
        raw = data.pop("default_ld_pin")
        t.default_ld_pin = encrypt(raw) if raw else None
    for k, v in data.items():
        setattr(t, k, v)
    t.updated_at = datetime.now(timezone.utc)
    await db.commit()
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.extensions), selectinload(Tenant.trunks), selectinload(Tenant.dids))
        .where(Tenant.id == tenant_id)
    )
    return _tenant_out(result.scalar_one())


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    await db.delete(t)
    await db.commit()
