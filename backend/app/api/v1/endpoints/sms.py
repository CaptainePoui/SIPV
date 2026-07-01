import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.sms import SMSConfig, SMSMessage, SMSProvider, SMSDirection, SMSStatus
from app.models.user import User

router = APIRouter()


# ── Config ────────────────────────────────────────────────────────────────────

class SMSConfigOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    account_sid: str | None
    from_number: str | None
    webhook_url: str | None
    monthly_limit: int | None
    is_active: bool

class SMSConfigUpsert(BaseModel):
    provider: SMSProvider
    api_key: str | None = None
    api_secret: str | None = None
    account_sid: str | None = None
    from_number: str | None = None
    webhook_url: str | None = None
    monthly_limit: int | None = None
    is_active: bool = True


def _config_out(c: SMSConfig) -> SMSConfigOut:
    return SMSConfigOut(id=c.id, tenant_id=c.tenant_id, provider=c.provider.value,
                        account_sid=c.account_sid, from_number=c.from_number,
                        webhook_url=c.webhook_url, monthly_limit=c.monthly_limit, is_active=c.is_active)


@router.get("/config/{tenant_id}", response_model=SMSConfigOut)
async def get_sms_config(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SMSConfig).where(SMSConfig.tenant_id == tenant_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Aucune configuration SMS pour ce tenant")
    return _config_out(c)


@router.put("/config/{tenant_id}", response_model=SMSConfigOut)
async def upsert_sms_config(tenant_id: uuid.UUID, payload: SMSConfigUpsert, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SMSConfig).where(SMSConfig.tenant_id == tenant_id))
    c = result.scalar_one_or_none()
    if c:
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(c, k, v)
    else:
        c = SMSConfig(tenant_id=tenant_id, **payload.model_dump())
        db.add(c)
    await db.commit()
    await db.refresh(c)
    return _config_out(c)


# ── Messages ──────────────────────────────────────────────────────────────────

class SMSMessageOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    direction: str
    status: str
    from_number: str
    to_number: str
    body: str
    provider_message_id: str | None
    num_segments: int | None
    cost: str | None
    error_code: str | None
    sent_at: datetime | None
    created_at: datetime

class SMSSend(BaseModel):
    to_number: str
    body: str
    from_number: str | None = None  # override default if needed


def _msg_out(m: SMSMessage) -> SMSMessageOut:
    return SMSMessageOut(id=m.id, tenant_id=m.tenant_id, direction=m.direction.value,
                         status=m.status.value, from_number=m.from_number, to_number=m.to_number,
                         body=m.body, provider_message_id=m.provider_message_id,
                         num_segments=m.num_segments, cost=m.cost, error_code=m.error_code,
                         sent_at=m.sent_at, created_at=m.created_at)


@router.get("/messages/tenant/{tenant_id}", response_model=list[SMSMessageOut])
async def list_messages(tenant_id: uuid.UUID, limit: int = 100, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(SMSMessage).where(SMSMessage.tenant_id == tenant_id)
        .order_by(SMSMessage.created_at.desc()).limit(limit)
    )
    return [_msg_out(m) for m in result.scalars().all()]


@router.post("/send/tenant/{tenant_id}", response_model=SMSMessageOut, status_code=status.HTTP_201_CREATED)
async def send_sms(tenant_id: uuid.UUID, payload: SMSSend, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    config_res = await db.execute(select(SMSConfig).where(SMSConfig.tenant_id == tenant_id, SMSConfig.is_active == True))
    config = config_res.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=400, detail="Aucune configuration SMS active pour ce tenant")

    from_num = payload.from_number or config.from_number
    if not from_num:
        raise HTTPException(status_code=400, detail="Numéro expéditeur requis")

    msg = SMSMessage(
        tenant_id=tenant_id,
        direction=SMSDirection.outbound,
        status=SMSStatus.queued,
        from_number=from_num,
        to_number=payload.to_number,
        body=payload.body,
        provider=config.provider.value,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    # Actual dispatch to provider (Twilio, Telnyx, etc.) would be done here via httpx
    # For now, the message is queued and marked sent by a worker / webhook response
    return _msg_out(msg)


@router.post("/webhook/{tenant_id}", status_code=200)
async def inbound_webhook(tenant_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Inbound SMS webhook — provider POSTs here when a message is received."""
    body = await request.json()
    # Normalize fields across providers (Twilio/Telnyx/Bandwidth common keys)
    from_num = (body.get("From") or body.get("from") or body.get("from_number") or "").strip()
    to_num = (body.get("To") or body.get("to") or body.get("to_number") or "").strip()
    text = (body.get("Body") or body.get("body") or body.get("text") or "").strip()
    provider_id = str(body.get("MessageSid") or body.get("message_id") or body.get("id") or "")

    if not (from_num and to_num and text):
        return {"status": "ignored", "reason": "missing fields"}

    msg = SMSMessage(
        tenant_id=tenant_id,
        direction=SMSDirection.inbound,
        status=SMSStatus.received,
        from_number=from_num,
        to_number=to_num,
        body=text,
        provider_message_id=provider_id or None,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    await db.commit()
    return {"status": "ok"}
