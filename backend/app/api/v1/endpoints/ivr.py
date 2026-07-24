import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.ivr import IVR, IVROption, Queue, QueueMember, RingGroup, RingGroupMember
from app.models.pending_change import PendingChange
from app.models.sip import SIPExtension
from app.models.user import User

router = APIRouter()

QUEUE_STRATEGIES = ["ringall", "leastrecent", "fewestcalls", "rrmemory", "random"]
DEST_TYPES = {"extension": "Extension", "ivr": "IVR", "queue": "File d'attente", "voicemail": "Messagerie"}


# ── IVR ───────────────────────────────────────────────────────────────────────

class IVROptionOut(BaseModel):
    id: uuid.UUID
    digit: str
    label: str | None
    destination_type: str
    destination: str

class IVROptionCreate(BaseModel):
    digit: str
    label: str | None = None
    destination_type: str
    destination: str

class IVROut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    greeting_text: str | None
    timeout_seconds: int
    max_retries: int
    invalid_destination: str | None
    timeout_destination: str | None
    is_active: bool
    created_at: datetime
    options: list[IVROptionOut]

class IVRCreate(BaseModel):
    name: str
    description: str | None = None
    greeting_text: str | None = None
    timeout_seconds: int = 10
    max_retries: int = 3
    invalid_destination: str | None = None
    timeout_destination: str | None = None
    options: list[IVROptionCreate] = []


def _ivr_out(ivr: IVR) -> IVROut:
    return IVROut(
        id=ivr.id, tenant_id=ivr.tenant_id, name=ivr.name, description=ivr.description,
        greeting_text=ivr.greeting_text, timeout_seconds=ivr.timeout_seconds, max_retries=ivr.max_retries,
        invalid_destination=ivr.invalid_destination, timeout_destination=ivr.timeout_destination,
        is_active=ivr.is_active, created_at=ivr.created_at,
        options=[IVROptionOut(id=o.id, digit=o.digit, label=o.label, destination_type=o.destination_type, destination=o.destination) for o in ivr.options],
    )


@router.get("/tenant/{tenant_id}", response_model=list[IVROut])
async def list_ivrs(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(IVR).options(selectinload(IVR.options)).where(IVR.tenant_id == tenant_id).order_by(IVR.name))
    return [_ivr_out(i) for i in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=IVROut, status_code=status.HTTP_201_CREATED)
async def create_ivr(tenant_id: uuid.UUID, payload: IVRCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.model_dump()
    options_data = data.pop("options", [])
    ivr = IVR(tenant_id=tenant_id, **data)
    db.add(ivr)
    await db.flush()
    for opt in options_data:
        db.add(IVROption(ivr_id=ivr.id, **opt))
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_ivr", entity_type="ivr",
                         entity_id=str(ivr.id), payload={"name": payload.name}, created_by=user.email))
    await db.commit()
    result = await db.execute(select(IVR).options(selectinload(IVR.options)).where(IVR.id == ivr.id))
    return _ivr_out(result.scalar_one())


@router.delete("/{ivr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ivr(ivr_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(IVR).where(IVR.id == ivr_id))
    ivr = result.scalar_one_or_none()
    if not ivr:
        raise HTTPException(status_code=404, detail="IVR introuvable")
    db.add(PendingChange(tenant_id=ivr.tenant_id, change_type="remove_ivr", entity_type="ivr",
                         entity_id=str(ivr_id), payload={"name": ivr.name}, created_by=user.email))
    await db.delete(ivr)
    await db.commit()


# ── Queues ────────────────────────────────────────────────────────────────────

class QueueMemberOut(BaseModel):
    id: uuid.UUID
    extension_username: str
    penalty: int
    agent_number: str | None
    agent_password: str | None
    is_dynamic: bool
    auto_login: bool
    pause_allowed: bool
    pause_reasons: str | None
    wrap_up_time_seconds: int
    skills: str | None

class QueueMemberCreate(BaseModel):
    extension_username: str
    penalty: int = 0
    agent_number: str | None = None
    agent_password: str | None = None
    is_dynamic: bool = True
    auto_login: bool = False
    pause_allowed: bool = True
    pause_reasons: str | None = None
    wrap_up_time_seconds: int = 0
    skills: str | None = None

class QueueMemberUpdate(BaseModel):
    penalty: int | None = None
    agent_number: str | None = None
    agent_password: str | None = None
    is_dynamic: bool | None = None
    auto_login: bool | None = None
    pause_allowed: bool | None = None
    pause_reasons: str | None = None
    wrap_up_time_seconds: int | None = None
    skills: str | None = None

def _member_out(m: QueueMember) -> QueueMemberOut:
    return QueueMemberOut(
        id=m.id, extension_username=m.extension_username, penalty=m.penalty,
        agent_number=m.agent_number, agent_password=m.agent_password, is_dynamic=m.is_dynamic,
        auto_login=m.auto_login, pause_allowed=m.pause_allowed, pause_reasons=m.pause_reasons,
        wrap_up_time_seconds=m.wrap_up_time_seconds, skills=m.skills,
    )

class QueueOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    queue_name: str
    strategy: str
    timeout_seconds: int
    max_wait_seconds: int
    no_answer_destination: str | None
    is_active: bool
    created_at: datetime
    members: list[QueueMemberOut]

class QueueCreate(BaseModel):
    name: str
    strategy: str = "rrmemory"
    timeout_seconds: int = 30
    max_wait_seconds: int = 120
    no_answer_destination: str | None = None
    members: list[str] = []  # list of extension usernames


def _queue_out(q: Queue) -> QueueOut:
    return QueueOut(
        id=q.id, tenant_id=q.tenant_id, name=q.name, queue_name=q.queue_name,
        strategy=q.strategy, timeout_seconds=q.timeout_seconds, max_wait_seconds=q.max_wait_seconds,
        no_answer_destination=q.no_answer_destination, is_active=q.is_active, created_at=q.created_at,
        members=[_member_out(m) for m in q.members],
    )


@router.get("/queues/tenant/{tenant_id}", response_model=list[QueueOut])
async def list_queues(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Queue).options(selectinload(Queue.members)).where(Queue.tenant_id == tenant_id).order_by(Queue.name))
    return [_queue_out(q) for q in result.scalars().all()]


@router.post("/queues/tenant/{tenant_id}", response_model=QueueOut, status_code=status.HTTP_201_CREATED)
async def create_queue(tenant_id: uuid.UUID, payload: QueueCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.strategy not in QUEUE_STRATEGIES:
        raise HTTPException(status_code=400, detail="Stratégie invalide")
    # Generate unique queue_name
    from sqlalchemy import text
    result = await db.execute(select(Queue).where(Queue.tenant_id == tenant_id))
    count = len(result.scalars().all())
    queue_name = f"q{count + 1:03d}_{payload.name.lower()[:20].replace(' ', '_')}"
    q = Queue(tenant_id=tenant_id, queue_name=queue_name, name=payload.name,
              strategy=payload.strategy, timeout_seconds=payload.timeout_seconds,
              max_wait_seconds=payload.max_wait_seconds, no_answer_destination=payload.no_answer_destination)
    db.add(q)
    await db.flush()
    for username in payload.members:
        db.add(QueueMember(queue_id=q.id, extension_username=username))
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_queue", entity_type="queue",
                         entity_id=str(q.id), payload={"queue_name": queue_name, "strategy": payload.strategy}, created_by=user.email))
    await db.commit()
    result = await db.execute(select(Queue).options(selectinload(Queue.members)).where(Queue.id == q.id))
    return _queue_out(result.scalar_one())


@router.delete("/queues/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_queue(queue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Queue).where(Queue.id == queue_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="File d'attente introuvable")
    db.add(PendingChange(tenant_id=q.tenant_id, change_type="remove_queue", entity_type="queue",
                         entity_id=str(queue_id), payload={"queue_name": q.queue_name}, created_by=user.email))
    await db.delete(q)
    await db.commit()


@router.post("/queues/{queue_id}/members", response_model=QueueMemberOut, status_code=status.HTTP_201_CREATED)
async def add_queue_member(queue_id: uuid.UUID, payload: QueueMemberCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    q = await db.get(Queue, queue_id)
    if not q:
        raise HTTPException(status_code=404, detail="File d'attente introuvable")
    m = QueueMember(queue_id=queue_id, **payload.model_dump())
    db.add(m)
    db.add(PendingChange(tenant_id=q.tenant_id, change_type="add_queue_member", entity_type="queue",
                         entity_id=str(queue_id), payload={"extension_username": payload.extension_username}, created_by=user.email))
    await db.commit()
    await db.refresh(m)
    return _member_out(m)


@router.put("/queues/members/{member_id}", response_model=QueueMemberOut)
async def update_queue_member(member_id: uuid.UUID, payload: QueueMemberUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(QueueMember).where(QueueMember.id == member_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(m, k, v)
    q = await db.get(Queue, m.queue_id)
    db.add(PendingChange(tenant_id=q.tenant_id, change_type="update_queue_member", entity_type="queue",
                         entity_id=str(m.queue_id), payload={"extension_username": m.extension_username, **{k: str(v) for k, v in data.items()}}, created_by=user.email))
    await db.commit()
    await db.refresh(m)
    return _member_out(m)


@router.delete("/queues/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_queue_member(member_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(QueueMember).where(QueueMember.id == member_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    q = await db.get(Queue, m.queue_id)
    db.add(PendingChange(tenant_id=q.tenant_id, change_type="remove_queue_member", entity_type="queue",
                         entity_id=str(m.queue_id), payload={"extension_username": m.extension_username}, created_by=user.email))
    await db.delete(m)
    await db.commit()


# ── Ring Groups ───────────────────────────────────────────────────────────────

class RingGroupMemberOut(BaseModel):
    id: uuid.UUID
    extension_id: uuid.UUID
    extension_username: str
    priority: int
    ring_order: int
    temporarily_excluded: bool

class RingGroupMemberCreate(BaseModel):
    extension_id: uuid.UUID
    priority: int = 0
    ring_order: int = 0
    temporarily_excluded: bool = False

class RingGroupMemberUpdate(BaseModel):
    priority: int | None = None
    ring_order: int | None = None
    temporarily_excluded: bool | None = None


class RingGroupOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    extension: str
    ring_strategy: str
    ring_time: int
    members: list[str]  # legacy CSV -- voir ring_members pour la donnee structuree (TASK-023.9)
    no_answer_destination: str | None
    is_active: bool
    created_at: datetime
    confirm_before_answer: bool
    schedule_id: uuid.UUID | None
    ring_members: list[RingGroupMemberOut] = []

class RingGroupCreate(BaseModel):
    name: str
    extension: str
    ring_strategy: str = "simultaneous"
    ring_time: int = 20
    members: list[str]
    no_answer_destination: str | None = None
    confirm_before_answer: bool = False
    schedule_id: uuid.UUID | None = None

class RingGroupUpdate(BaseModel):
    name: str | None = None
    ring_strategy: str | None = None
    ring_time: int | None = None
    no_answer_destination: str | None = None
    is_active: bool | None = None
    confirm_before_answer: bool | None = None
    schedule_id: uuid.UUID | None = None


def _rg_out(r: RingGroup) -> RingGroupOut:
    return RingGroupOut(
        id=r.id, tenant_id=r.tenant_id, name=r.name, extension=r.extension,
        ring_strategy=r.ring_strategy, ring_time=r.ring_time,
        members=[m.strip() for m in r.members.split(",") if m.strip()],
        no_answer_destination=r.no_answer_destination, is_active=r.is_active, created_at=r.created_at,
        confirm_before_answer=r.confirm_before_answer, schedule_id=r.schedule_id,
        ring_members=[
            RingGroupMemberOut(
                id=m.id, extension_id=m.extension_id,
                extension_username=m.extension.username if m.extension else "",
                priority=m.priority, ring_order=m.ring_order, temporarily_excluded=m.temporarily_excluded,
            ) for m in (r.ring_members or [])
        ],
    )


@router.get("/ring-groups/tenant/{tenant_id}", response_model=list[RingGroupOut])
async def list_ring_groups(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(RingGroup).options(selectinload(RingGroup.ring_members).selectinload(RingGroupMember.extension))
        .where(RingGroup.tenant_id == tenant_id).order_by(RingGroup.extension)
    )
    return [_rg_out(r) for r in result.scalars().all()]


@router.put("/ring-groups/{rg_id}", response_model=RingGroupOut)
async def update_ring_group(rg_id: uuid.UUID, payload: RingGroupUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(RingGroup).options(selectinload(RingGroup.ring_members).selectinload(RingGroupMember.extension))
        .where(RingGroup.id == rg_id)
    )
    rg = result.scalar_one_or_none()
    if not rg:
        raise HTTPException(status_code=404, detail="Groupe d'appels introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rg, k, v)
    db.add(PendingChange(tenant_id=rg.tenant_id, change_type="update_ring_group", entity_type="ring_group",
                         entity_id=str(rg_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email))
    await db.commit()
    return _rg_out(rg)


@router.post("/ring-groups/{rg_id}/members", response_model=RingGroupMemberOut, status_code=status.HTTP_201_CREATED)
async def add_ring_group_member(rg_id: uuid.UUID, payload: RingGroupMemberCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rg = await db.get(RingGroup, rg_id)
    if not rg:
        raise HTTPException(status_code=404, detail="Groupe d'appels introuvable")
    ext = await db.get(SIPExtension, payload.extension_id)
    if not ext:
        raise HTTPException(status_code=404, detail="Poste introuvable")
    m = RingGroupMember(ring_group_id=rg_id, **payload.model_dump())
    db.add(m)
    db.add(PendingChange(tenant_id=rg.tenant_id, change_type="add_ring_group_member", entity_type="ring_group",
                         entity_id=str(rg_id), payload={"extension_username": ext.username}, created_by=user.email))
    await db.commit()
    await db.refresh(m)
    return RingGroupMemberOut(id=m.id, extension_id=m.extension_id, extension_username=ext.username,
                              priority=m.priority, ring_order=m.ring_order, temporarily_excluded=m.temporarily_excluded)


@router.put("/ring-groups/members/{member_id}", response_model=RingGroupMemberOut)
async def update_ring_group_member(member_id: uuid.UUID, payload: RingGroupMemberUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(RingGroupMember).where(RingGroupMember.id == member_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    ext = await db.get(SIPExtension, m.extension_id)
    rg = await db.get(RingGroup, m.ring_group_id)
    db.add(PendingChange(tenant_id=rg.tenant_id, change_type="update_ring_group_member", entity_type="ring_group",
                         entity_id=str(m.ring_group_id), payload=payload.model_dump(exclude_unset=True), created_by=user.email))
    await db.commit()
    await db.refresh(m)
    return RingGroupMemberOut(id=m.id, extension_id=m.extension_id, extension_username=ext.username if ext else "",
                              priority=m.priority, ring_order=m.ring_order, temporarily_excluded=m.temporarily_excluded)


@router.delete("/ring-groups/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ring_group_member(member_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(RingGroupMember).where(RingGroupMember.id == member_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    rg = await db.get(RingGroup, m.ring_group_id)
    db.add(PendingChange(tenant_id=rg.tenant_id, change_type="remove_ring_group_member", entity_type="ring_group",
                         entity_id=str(m.ring_group_id), payload={"member_id": str(member_id)}, created_by=user.email))
    await db.delete(m)
    await db.commit()


@router.post("/ring-groups/tenant/{tenant_id}", response_model=RingGroupOut, status_code=status.HTTP_201_CREATED)
async def create_ring_group(tenant_id: uuid.UUID, payload: RingGroupCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rg = RingGroup(tenant_id=tenant_id, name=payload.name, extension=payload.extension,
                   ring_strategy=payload.ring_strategy, ring_time=payload.ring_time,
                   members=",".join(payload.members), no_answer_destination=payload.no_answer_destination,
                   confirm_before_answer=payload.confirm_before_answer, schedule_id=payload.schedule_id)
    db.add(rg)
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_ring_group", entity_type="ring_group",
                         entity_id=str(rg.id), payload={"extension": payload.extension, "members": payload.members}, created_by=user.email))
    await db.commit()
    result = await db.execute(
        select(RingGroup).options(selectinload(RingGroup.ring_members).selectinload(RingGroupMember.extension))
        .where(RingGroup.id == rg.id)
    )
    return _rg_out(result.scalar_one())


@router.delete("/ring-groups/{rg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ring_group(rg_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(RingGroup).where(RingGroup.id == rg_id))
    rg = result.scalar_one_or_none()
    if not rg:
        raise HTTPException(status_code=404, detail="Groupe d'appels introuvable")
    db.add(PendingChange(tenant_id=rg.tenant_id, change_type="remove_ring_group", entity_type="ring_group",
                         entity_id=str(rg_id), payload={"name": rg.name}, created_by=user.email))
    await db.delete(rg)
    await db.commit()
