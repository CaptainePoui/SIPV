import uuid
import csv
import io
import math
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.cdr import CDR, RatePrefix
from app.models.user import User

router = APIRouter()


# ── Rate Prefixes ────────────────────────────────────────────────────────────

class PrefixOut(BaseModel):
    id: uuid.UUID
    prefix: str
    description: str | None
    country: str | None
    region: str | None
    rate_per_minute: Decimal
    min_duration: int
    increment: int
    is_active: bool

class PrefixCreate(BaseModel):
    prefix: str
    description: str | None = None
    country: str | None = None
    region: str | None = None
    rate_per_minute: Decimal
    min_duration: int = 6
    increment: int = 6

class PrefixUpdate(BaseModel):
    description: str | None = None
    country: str | None = None
    region: str | None = None
    rate_per_minute: Decimal | None = None
    min_duration: int | None = None
    increment: int | None = None
    is_active: bool | None = None


def _prefix_out(p: RatePrefix) -> PrefixOut:
    return PrefixOut(id=p.id, prefix=p.prefix, description=p.description, country=p.country,
                     region=p.region, rate_per_minute=p.rate_per_minute, min_duration=p.min_duration,
                     increment=p.increment, is_active=p.is_active)


@router.get("/prefixes", response_model=list[PrefixOut])
async def list_prefixes(active_only: bool = True, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(RatePrefix).order_by(RatePrefix.prefix)
    if active_only:
        q = q.where(RatePrefix.is_active == True)
    result = await db.execute(q)
    return [_prefix_out(p) for p in result.scalars().all()]


@router.post("/prefixes", response_model=PrefixOut, status_code=status.HTTP_201_CREATED)
async def create_prefix(payload: PrefixCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    existing = await db.execute(select(RatePrefix).where(RatePrefix.prefix == payload.prefix))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ce préfixe existe déjà")
    p = RatePrefix(**payload.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _prefix_out(p)


@router.put("/prefixes/{prefix_id}", response_model=PrefixOut)
async def update_prefix(prefix_id: uuid.UUID, payload: PrefixUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(RatePrefix).where(RatePrefix.id == prefix_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Préfixe introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return _prefix_out(p)


@router.delete("/prefixes/{prefix_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prefix(prefix_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(RatePrefix).where(RatePrefix.id == prefix_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Préfixe introuvable")
    await db.delete(p)
    await db.commit()


@router.post("/prefixes/import", status_code=200)
async def import_prefixes_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Import rate prefixes from CSV. Expected columns: prefix,description,country,region,rate_per_minute
    Existing prefixes are updated; new ones are inserted."""
    if not file.filename or not (file.filename.endswith('.csv') or file.filename.endswith('.txt')):
        raise HTTPException(status_code=400, detail="Fichier CSV requis (.csv ou .txt)")
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')  # handle BOM
    except UnicodeDecodeError:
        text = content.decode('latin-1')
    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    updated = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        try:
            prefix = (row.get('prefix') or row.get('Prefix') or '').strip()
            rate_str = (row.get('rate_per_minute') or row.get('Rate') or row.get('rate') or '').strip()
            if not prefix or not rate_str:
                continue
            rate = Decimal(rate_str.replace(',', '.'))
            existing = await db.execute(select(RatePrefix).where(RatePrefix.prefix == prefix))
            p = existing.scalar_one_or_none()
            if p:
                p.rate_per_minute = rate
                p.description = (row.get('description') or row.get('Description') or p.description or '').strip() or None
                p.country = (row.get('country') or row.get('Country') or p.country or '').strip() or None
                p.region = (row.get('region') or row.get('Region') or p.region or '').strip() or None
                updated += 1
            else:
                p = RatePrefix(
                    prefix=prefix,
                    rate_per_minute=rate,
                    description=(row.get('description') or row.get('Description') or '').strip() or None,
                    country=(row.get('country') or row.get('Country') or '').strip() or None,
                    region=(row.get('region') or row.get('Region') or '').strip() or None,
                )
                db.add(p)
                inserted += 1
        except Exception as e:
            errors.append(f"Ligne {i}: {e}")
    await db.commit()
    return {"inserted": inserted, "updated": updated, "errors": errors}


# ── CDR ──────────────────────────────────────────────────────────────────────

class CDROut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    src: str | None
    dst: str | None
    disposition: str | None
    direction: str | None
    billsec: int | None
    start_time: datetime | None
    cost: Decimal | None
    rate_per_minute: Decimal | None
    uniqueid: str | None

class CDRSummary(BaseModel):
    total_calls: int
    answered_calls: int
    total_billsec: int
    total_cost: Decimal

class PaginatedCDR(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CDROut]


@router.get("/tenant/{tenant_id}", response_model=PaginatedCDR)
async def list_cdr(
    tenant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    direction: str | None = Query(None),
    disposition: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    filters = [CDR.tenant_id == tenant_id]
    if direction:
        filters.append(CDR.direction == direction)
    if disposition:
        filters.append(CDR.disposition == disposition)
    if date_from:
        filters.append(CDR.start_time >= date_from)
    if date_to:
        filters.append(CDR.start_time <= date_to)

    total_res = await db.execute(select(func.count()).select_from(CDR).where(and_(*filters)))
    total = total_res.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(CDR).where(and_(*filters))
        .order_by(CDR.start_time.desc())
        .offset(offset).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedCDR(
        total=total, page=page, page_size=page_size,
        items=[CDROut(id=c.id, tenant_id=c.tenant_id, src=c.src, dst=c.dst, disposition=c.disposition,
                      direction=c.direction, billsec=c.billsec, start_time=c.start_time,
                      cost=c.cost, rate_per_minute=c.rate_per_minute, uniqueid=c.uniqueid)
               for c in items]
    )


@router.get("/tenant/{tenant_id}/summary", response_model=CDRSummary)
async def cdr_summary(
    tenant_id: uuid.UUID,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    filters = [CDR.tenant_id == tenant_id]
    if date_from:
        filters.append(CDR.start_time >= date_from)
    if date_to:
        filters.append(CDR.start_time <= date_to)

    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(CDR.billsec).label("billsec"),
            func.sum(CDR.cost).label("cost"),
            func.count().filter(CDR.disposition == "ANSWERED").label("answered"),
        ).where(and_(*filters))
    )
    row = result.one()
    return CDRSummary(
        total_calls=row.total or 0,
        answered_calls=row.answered or 0,
        total_billsec=row.billsec or 0,
        total_cost=row.cost or Decimal("0"),
    )


def _calculate_cost(billsec: int, p: RatePrefix) -> Decimal:
    """Calculate call cost using prefix rate with min_duration and increment."""
    if billsec <= 0:
        return Decimal("0")
    billed = max(billsec, p.min_duration)
    increments = math.ceil((billed - p.min_duration) / p.increment)
    billed_seconds = p.min_duration + increments * p.increment
    return (Decimal(str(billed_seconds)) / Decimal("60") * p.rate_per_minute).quantize(Decimal("0.000001"))


@router.post("/rate/{cdr_id}", status_code=200)
async def rate_cdr(cdr_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Find matching prefix (longest-match) and compute cost for a CDR record."""
    result = await db.execute(select(CDR).where(CDR.id == cdr_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="CDR introuvable")
    if not c.dst:
        raise HTTPException(status_code=400, detail="CDR sans numéro de destination")

    # Longest-prefix match
    all_prefixes = await db.execute(select(RatePrefix).where(RatePrefix.is_active == True))
    prefix = None
    best_len = -1
    dst_digits = ''.join(filter(str.isdigit, c.dst))
    for p in all_prefixes.scalars().all():
        pfx_digits = ''.join(filter(str.isdigit, p.prefix))
        if dst_digits.startswith(pfx_digits) and len(pfx_digits) > best_len:
            prefix = p
            best_len = len(pfx_digits)

    if not prefix:
        return {"matched": False, "dst": c.dst}

    cost = _calculate_cost(c.billsec or 0, prefix)
    c.prefix_id = prefix.id
    c.rate_per_minute = prefix.rate_per_minute
    c.cost = cost
    await db.commit()
    return {"matched": True, "prefix": prefix.prefix, "rate_per_minute": str(prefix.rate_per_minute), "cost": str(cost)}
