import uuid
import hmac
import hashlib
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.models.user import User

router = APIRouter()

# Known event types for SIPV → ERPCRM sync
KNOWN_EVENTS = [
    "tenant.created", "tenant.updated", "tenant.deleted",
    "extension.created", "extension.updated", "extension.deleted",
    "did.created", "did.updated", "did.deleted",
    "call.started", "call.ended",
    "cdr.created",
    "security.fraud_alert", "security.ip_blocked",
]


class EndpointOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime

class EndpointCreate(BaseModel):
    name: str
    url: str
    secret: str | None = None
    event_types: list[str]

class EndpointUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    event_types: list[str] | None = None
    is_active: bool | None = None

class DeliveryOut(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    status_code: int | None
    attempt: int
    success: bool
    error_message: str | None
    next_retry_at: datetime | None
    created_at: datetime


def _ep_out(e: WebhookEndpoint) -> EndpointOut:
    return EndpointOut(id=e.id, name=e.name, url=e.url,
                       event_types=e.event_types.split(","), is_active=e.is_active, created_at=e.created_at)


@router.get("/endpoints", response_model=list[EndpointOut])
async def list_endpoints(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(WebhookEndpoint).order_by(WebhookEndpoint.name))
    return [_ep_out(e) for e in result.scalars().all()]


@router.post("/endpoints", response_model=EndpointOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(payload: EndpointCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    e = WebhookEndpoint(name=payload.name, url=payload.url, secret=payload.secret,
                        event_types=",".join(payload.event_types))
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return _ep_out(e)


@router.put("/endpoints/{ep_id}", response_model=EndpointOut)
async def update_endpoint(ep_id: uuid.UUID, payload: EndpointUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == ep_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "event_types" in data:
        data["event_types"] = ",".join(data["event_types"])
    for k, v in data.items():
        setattr(e, k, v)
    await db.commit()
    await db.refresh(e)
    return _ep_out(e)


@router.delete("/endpoints/{ep_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(ep_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == ep_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    await db.delete(e)
    await db.commit()


@router.get("/deliveries/{ep_id}", response_model=list[DeliveryOut])
async def list_deliveries(ep_id: uuid.UUID, limit: int = 100, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.endpoint_id == ep_id)
        .order_by(WebhookDelivery.created_at.desc()).limit(limit)
    )
    return [DeliveryOut(id=d.id, endpoint_id=d.endpoint_id, event_type=d.event_type,
                        status_code=d.status_code, attempt=d.attempt, success=d.success,
                        error_message=d.error_message, next_retry_at=d.next_retry_at, created_at=d.created_at)
            for d in result.scalars().all()]


@router.post("/dispatch", status_code=202)
async def dispatch_event(event_type: str, payload: dict, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Dispatch an event to all active webhook endpoints that subscribe to it.
    Returns a summary of deliveries queued."""
    result = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.is_active == True))
    endpoints = [e for e in result.scalars().all() if event_type in e.event_types.split(",")]

    body = json.dumps({"event": event_type, "data": payload, "ts": datetime.now(timezone.utc).isoformat()})

    deliveries = []
    for ep in endpoints:
        headers_meta = {}
        if ep.secret:
            sig = hmac.new(ep.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers_meta["X-SIPV-Signature"] = f"sha256={sig}"

        delivery = WebhookDelivery(endpoint_id=ep.id, event_type=event_type, payload=payload)
        db.add(delivery)
        deliveries.append({"endpoint": ep.name, "url": ep.url})

        # Actual HTTP dispatch would go here via httpx (background task / Celery)
        # For now, delivery is recorded and would be picked up by a worker
        delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=5)

    await db.commit()
    return {"queued": len(deliveries), "endpoints": deliveries}
