import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.voicemail import VoicemailBox, VoicemailMessage
from app.models.pending_change import PendingChange
from app.models.user import User

router = APIRouter()


class VoicemailOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    extension_id: uuid.UUID | None
    mailbox: str
    context: str
    fullname: str
    email: str | None
    email_on_new: bool
    attach_message: bool
    delete_after_email: bool
    max_messages: int
    is_active: bool
    created_at: datetime

class VoicemailCreate(BaseModel):
    extension_id: uuid.UUID | None = None
    mailbox: str
    fullname: str
    email: str | None = None
    password: str | None = None
    email_on_new: bool = True
    attach_message: bool = True
    delete_after_email: bool = False
    max_messages: int = 100
    context: str = "default"

class VoicemailUpdate(BaseModel):
    fullname: str | None = None
    email: str | None = None
    password: str | None = None
    email_on_new: bool | None = None
    attach_message: bool | None = None
    delete_after_email: bool | None = None
    max_messages: int | None = None
    is_active: bool | None = None

class VoicemailMessageOut(BaseModel):
    id: uuid.UUID
    msgnum: int
    folder: str
    callerid: str | None
    duration: int | None
    is_read: bool
    created_at: datetime


def _out(v: VoicemailBox) -> VoicemailOut:
    return VoicemailOut(
        id=v.id, tenant_id=v.tenant_id, extension_id=v.extension_id, mailbox=v.mailbox,
        context=v.context, fullname=v.fullname, email=v.email, email_on_new=v.email_on_new,
        attach_message=v.attach_message, delete_after_email=v.delete_after_email,
        max_messages=v.max_messages, is_active=v.is_active, created_at=v.created_at,
    )


@router.get("/tenant/{tenant_id}", response_model=list[VoicemailOut])
async def list_voicemails(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id).order_by(VoicemailBox.mailbox))
    return [_out(v) for v in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=VoicemailOut, status_code=status.HTTP_201_CREATED)
async def create_voicemail(tenant_id: uuid.UUID, payload: VoicemailCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    password = payload.password or str(secrets.randbelow(9000) + 1000)
    data = payload.model_dump()
    data.pop("password", None)
    v = VoicemailBox(tenant_id=tenant_id, password=password, **data)
    db.add(v)
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_voicemail", entity_type="voicemail",
                         payload={"mailbox": payload.mailbox, "context": payload.context, "email": payload.email},
                         created_by=user.email))
    await db.commit()
    await db.refresh(v)
    return _out(v)


@router.put("/{vm_id}", response_model=VoicemailOut)
async def update_voicemail(vm_id: uuid.UUID, payload: VoicemailUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, val in data.items():
        setattr(v, k, val)
    db.add(PendingChange(tenant_id=v.tenant_id, change_type="update_voicemail", entity_type="voicemail",
                         entity_id=str(vm_id), payload={k: str(v) for k, v in data.items()}, created_by=user.email))
    await db.commit()
    await db.refresh(v)
    return _out(v)


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voicemail(vm_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")
    db.add(PendingChange(tenant_id=v.tenant_id, change_type="remove_voicemail", entity_type="voicemail",
                         entity_id=str(vm_id), payload={"mailbox": v.mailbox}, created_by=user.email))
    await db.delete(v)
    await db.commit()


@router.get("/{vm_id}/messages", response_model=list[VoicemailMessageOut])
async def list_messages(vm_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(VoicemailMessage).where(VoicemailMessage.mailbox_id == vm_id).order_by(VoicemailMessage.created_at.desc())
    )
    msgs = result.scalars().all()
    return [VoicemailMessageOut(id=m.id, msgnum=m.msgnum, folder=m.folder, callerid=m.callerid,
                                duration=m.duration, is_read=m.is_read, created_at=m.created_at)
            for m in msgs]
