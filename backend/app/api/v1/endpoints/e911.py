import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.e911 import E911Address, DID911Assignment
from app.models.user import User

router = APIRouter()


class AddressOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    label: str
    civic_number: str
    street_name: str
    unit: str | None
    city: str
    province: str
    postal_code: str
    country: str
    is_validated: bool
    carrier_reference: str | None
    notes: str | None
    is_active: bool

class AddressCreate(BaseModel):
    label: str
    civic_number: str
    street_name: str
    unit: str | None = None
    city: str
    province: str
    postal_code: str
    country: str = "CA"
    notes: str | None = None

class AddressUpdate(BaseModel):
    label: str | None = None
    civic_number: str | None = None
    street_name: str | None = None
    unit: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    is_validated: bool | None = None
    carrier_reference: str | None = None
    notes: str | None = None
    is_active: bool | None = None

class AssignmentOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    did_id: uuid.UUID
    e911_address_id: uuid.UUID
    emergency_trunk_id: uuid.UUID | None
    alert_email: str | None
    is_active: bool

class AssignmentCreate(BaseModel):
    did_id: uuid.UUID
    e911_address_id: uuid.UUID
    emergency_trunk_id: uuid.UUID | None = None
    alert_email: str | None = None


def _addr_out(a: E911Address) -> AddressOut:
    return AddressOut(id=a.id, tenant_id=a.tenant_id, label=a.label, civic_number=a.civic_number,
                      street_name=a.street_name, unit=a.unit, city=a.city, province=a.province,
                      postal_code=a.postal_code, country=a.country, is_validated=a.is_validated,
                      carrier_reference=a.carrier_reference, notes=a.notes, is_active=a.is_active)


# ── E911 Addresses ────────────────────────────────────────────────────────────

@router.get("/addresses/tenant/{tenant_id}", response_model=list[AddressOut])
async def list_addresses(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(E911Address).where(E911Address.tenant_id == tenant_id).order_by(E911Address.label))
    return [_addr_out(a) for a in result.scalars().all()]


@router.post("/addresses/tenant/{tenant_id}", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(tenant_id: uuid.UUID, payload: AddressCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    a = E911Address(tenant_id=tenant_id, **payload.model_dump())
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return _addr_out(a)


@router.put("/addresses/{addr_id}", response_model=AddressOut)
async def update_address(addr_id: uuid.UUID, payload: AddressUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(E911Address).where(E911Address.id == addr_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Adresse 911 introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await db.commit()
    await db.refresh(a)
    return _addr_out(a)


@router.delete("/addresses/{addr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(addr_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(E911Address).where(E911Address.id == addr_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Adresse 911 introuvable")
    await db.delete(a)
    await db.commit()


# ── DID 911 Assignments ───────────────────────────────────────────────────────

@router.get("/assignments/tenant/{tenant_id}", response_model=list[AssignmentOut])
async def list_assignments(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(DID911Assignment).where(DID911Assignment.tenant_id == tenant_id))
    return [AssignmentOut(id=x.id, tenant_id=x.tenant_id, did_id=x.did_id,
                          e911_address_id=x.e911_address_id, emergency_trunk_id=x.emergency_trunk_id,
                          alert_email=x.alert_email, is_active=x.is_active)
            for x in result.scalars().all()]


@router.post("/assignments/tenant/{tenant_id}", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(tenant_id: uuid.UUID, payload: AssignmentCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    # Enforce one address per DID
    existing = await db.execute(select(DID911Assignment).where(DID911Assignment.did_id == payload.did_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ce DID a déjà une adresse 911 assignée")
    x = DID911Assignment(tenant_id=tenant_id, **payload.model_dump())
    db.add(x)
    await db.commit()
    await db.refresh(x)
    return AssignmentOut(id=x.id, tenant_id=x.tenant_id, did_id=x.did_id,
                         e911_address_id=x.e911_address_id, emergency_trunk_id=x.emergency_trunk_id,
                         alert_email=x.alert_email, is_active=x.is_active)


@router.put("/assignments/{assign_id}", response_model=AssignmentOut)
async def update_assignment(assign_id: uuid.UUID, payload: AssignmentCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(DID911Assignment).where(DID911Assignment.id == assign_id))
    x = result.scalar_one_or_none()
    if not x:
        raise HTTPException(status_code=404, detail="Assignment 911 introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(x, k, v)
    await db.commit()
    await db.refresh(x)
    return AssignmentOut(id=x.id, tenant_id=x.tenant_id, did_id=x.did_id,
                         e911_address_id=x.e911_address_id, emergency_trunk_id=x.emergency_trunk_id,
                         alert_email=x.alert_email, is_active=x.is_active)


@router.delete("/assignments/{assign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assign_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(DID911Assignment).where(DID911Assignment.id == assign_id))
    x = result.scalar_one_or_none()
    if not x:
        raise HTTPException(status_code=404, detail="Assignment 911 introuvable")
    await db.delete(x)
    await db.commit()


@router.get("/dids-without-911/tenant/{tenant_id}")
async def dids_without_911(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Returns list of DID IDs that have no 911 assignment — useful for compliance alerts."""
    from app.models.sip import TenantDID
    all_dids = await db.execute(select(TenantDID.id, TenantDID.did_number).where(TenantDID.tenant_id == tenant_id))
    assigned = await db.execute(select(DID911Assignment.did_id).where(DID911Assignment.tenant_id == tenant_id))
    assigned_ids = {r[0] for r in assigned.all()}
    missing = [{"did_id": str(r[0]), "did_number": r[1]} for r in all_dids.all() if r[0] not in assigned_ids]
    return {"count": len(missing), "dids_without_911": missing}
