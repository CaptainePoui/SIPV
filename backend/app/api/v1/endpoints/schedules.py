import uuid
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.schedule import Schedule, ScheduleRule, Holiday
from app.models.user import User

router = APIRouter()


# ── Schedules ─────────────────────────────────────────────────────────────────

class RuleOut(BaseModel):
    id: uuid.UUID
    days_of_week: list[int]
    open_time: str
    close_time: str
    label: str | None

class ScheduleOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    timezone: str
    closed_destination_type: str | None
    closed_destination: str | None
    is_active: bool
    rules: list[RuleOut] = []

class RuleCreate(BaseModel):
    days_of_week: list[int]  # 0=Mon..6=Sun
    open_time: str            # "09:00"
    close_time: str           # "17:00"
    label: str | None = None

class ScheduleCreate(BaseModel):
    name: str
    timezone: str = "America/Montreal"
    closed_destination_type: str | None = None
    closed_destination: str | None = None
    rules: list[RuleCreate] = []

class ScheduleUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    closed_destination_type: str | None = None
    closed_destination: str | None = None
    is_active: bool | None = None


def _rule_out(r: ScheduleRule) -> RuleOut:
    return RuleOut(id=r.id, days_of_week=[int(d) for d in r.days_of_week.split(",") if d],
                   open_time=str(r.open_time)[:5], close_time=str(r.close_time)[:5], label=r.label)

def _sched_out(s: Schedule, rules: list[ScheduleRule] = []) -> ScheduleOut:
    return ScheduleOut(id=s.id, tenant_id=s.tenant_id, name=s.name, timezone=s.timezone,
                       closed_destination_type=s.closed_destination_type,
                       closed_destination=s.closed_destination, is_active=s.is_active,
                       rules=[_rule_out(r) for r in rules])


@router.get("/tenant/{tenant_id}", response_model=list[ScheduleOut])
async def list_schedules(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    scheds = await db.execute(select(Schedule).where(Schedule.tenant_id == tenant_id).order_by(Schedule.name))
    result = []
    for s in scheds.scalars().all():
        rules = await db.execute(select(ScheduleRule).where(ScheduleRule.schedule_id == s.id))
        result.append(_sched_out(s, rules.scalars().all()))
    return result


@router.post("/tenant/{tenant_id}", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(tenant_id: uuid.UUID, payload: ScheduleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    s = Schedule(tenant_id=tenant_id, name=payload.name, timezone=payload.timezone,
                 closed_destination_type=payload.closed_destination_type,
                 closed_destination=payload.closed_destination)
    db.add(s)
    await db.flush()
    rules = []
    for r in payload.rules:
        rule = ScheduleRule(schedule_id=s.id, days_of_week=",".join(str(d) for d in r.days_of_week),
                            open_time=dt.time.fromisoformat(r.open_time),
                            close_time=dt.time.fromisoformat(r.close_time), label=r.label)
        db.add(rule)
        rules.append(rule)
    await db.commit()
    await db.refresh(s)
    return _sched_out(s, rules)


@router.put("/{sched_id}", response_model=ScheduleOut)
async def update_schedule(sched_id: uuid.UUID, payload: ScheduleUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Schedule).where(Schedule.id == sched_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Horaire introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    rules = await db.execute(select(ScheduleRule).where(ScheduleRule.schedule_id == sched_id))
    await db.commit()
    await db.refresh(s)
    return _sched_out(s, rules.scalars().all())


@router.delete("/{sched_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(sched_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Schedule).where(Schedule.id == sched_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Horaire introuvable")
    await db.delete(s)
    await db.commit()


@router.post("/{sched_id}/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def add_rule(sched_id: uuid.UUID, payload: RuleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    rule = ScheduleRule(schedule_id=sched_id, days_of_week=",".join(str(d) for d in payload.days_of_week),
                        open_time=dt.time.fromisoformat(payload.open_time),
                        close_time=dt.time.fromisoformat(payload.close_time), label=payload.label)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_out(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ScheduleRule).where(ScheduleRule.id == rule_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    await db.delete(r)
    await db.commit()


# ── Holidays ──────────────────────────────────────────────────────────────────

class HolidayOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    date: dt.date
    name: str
    override_destination_type: str | None
    override_destination: str | None
    recurring: bool

class HolidayCreate(BaseModel):
    date: dt.date
    name: str
    override_destination_type: str | None = None
    override_destination: str | None = None
    recurring: bool = False


@router.get("/holidays/tenant/{tenant_id}", response_model=list[HolidayOut])
async def list_holidays(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Holiday).where(Holiday.tenant_id == tenant_id).order_by(Holiday.date))
    return [HolidayOut(id=h.id, tenant_id=h.tenant_id, date=h.date, name=h.name,
                       override_destination_type=h.override_destination_type,
                       override_destination=h.override_destination, recurring=h.recurring)
            for h in result.scalars().all()]


@router.post("/holidays/tenant/{tenant_id}", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
async def create_holiday(tenant_id: uuid.UUID, payload: HolidayCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    h = Holiday(tenant_id=tenant_id, **payload.model_dump())
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return HolidayOut(id=h.id, tenant_id=h.tenant_id, date=h.date, name=h.name,
                      override_destination_type=h.override_destination_type,
                      override_destination=h.override_destination, recurring=h.recurring)


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(holiday_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Holiday).where(Holiday.id == holiday_id))
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Jour férié introuvable")
    await db.delete(h)
    await db.commit()


@router.get("/{sched_id}/is-open", response_model=dict)
async def check_is_open(sched_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Check if schedule is currently open. Returns {is_open, reason}."""
    import zoneinfo
    result = await db.execute(select(Schedule).where(Schedule.id == sched_id))
    s = result.scalar_one_or_none()
    if not s or not s.is_active:
        return {"is_open": False, "reason": "schedule_inactive"}

    try:
        tz = zoneinfo.ZoneInfo(s.timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/Montreal")

    now_local = dt.datetime.now(tz)
    today = now_local.date()
    now_time = now_local.time().replace(second=0, microsecond=0)
    weekday = now_local.weekday()  # 0=Mon..6=Sun

    # Check holidays
    holidays = await db.execute(select(Holiday).where(Holiday.tenant_id == s.tenant_id))
    for h in holidays.scalars().all():
        hdate = h.date
        if h.recurring:
            match = hdate.month == today.month and hdate.day == today.day
        else:
            match = hdate == today
        if match:
            return {"is_open": False, "reason": "holiday", "holiday": h.name}

    # Check schedule rules
    rules = await db.execute(select(ScheduleRule).where(ScheduleRule.schedule_id == sched_id))
    for r in rules.scalars().all():
        days = [int(d) for d in r.days_of_week.split(",") if d]
        if weekday in days and r.open_time <= now_time < r.close_time:
            return {"is_open": True, "reason": "within_hours", "rule_label": r.label}

    return {"is_open": False, "reason": "outside_hours",
            "closed_destination_type": s.closed_destination_type,
            "closed_destination": s.closed_destination}
