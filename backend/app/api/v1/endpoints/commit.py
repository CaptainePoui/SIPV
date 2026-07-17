"""
Commit/Checkpoint system for FreeSWITCH config changes.
Pending changes are queued for audit/tracking; applying them means invalidating
FreeSWITCH's mod_xml_curl cache so it re-fetches live directory/dialplan XML
from the DB (see xml_curl.py). There is no local realtime table to write to,
unlike the abandoned Asterisk PJSIP Realtime approach.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.esl import get_esl, ESLClient
from app.api.v1.endpoints.auth import get_current_user
from app.models.pending_change import PendingChange
from app.models.sip import SIPExtension, SIPTrunk, TenantDID
from app.models.user import User

router = APIRouter()


class PendingChangeOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    change_type: str
    entity_type: str
    entity_id: str | None
    payload: dict
    status: str
    error_message: str | None
    created_by: str | None
    created_at: datetime
    applied_at: datetime | None


class CommitResult(BaseModel):
    tenant_id: uuid.UUID
    applied: int
    failed: int
    errors: list[str]


async def _apply_change_to_freeswitch(esl: ESLClient) -> str | None:
    """
    Invalidate FreeSWITCH's mod_xml_curl cache so it re-fetches live directory/dialplan
    XML from the DB on the next lookup (see xml_curl.py). FreeSWITCH has no local realtime
    table to write to — the config is generated on-demand from PostgreSQL.
    Returns an error message on failure, None on success.
    """
    try:
        await esl.reload_xml()
        return None
    except Exception as e:
        return str(e)


@router.get("/pending/{tenant_id}", response_model=list[PendingChangeOut])
async def list_pending(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(PendingChange)
        .where(PendingChange.tenant_id == tenant_id, PendingChange.status == "pending")
        .order_by(PendingChange.created_at)
    )
    changes = result.scalars().all()
    return [PendingChangeOut(
        id=c.id, tenant_id=c.tenant_id, change_type=c.change_type, entity_type=c.entity_type,
        entity_id=c.entity_id, payload=c.payload, status=c.status, error_message=c.error_message,
        created_by=c.created_by, created_at=c.created_at, applied_at=c.applied_at,
    ) for c in changes]


@router.post("/commit/{tenant_id}", response_model=CommitResult)
async def commit_changes(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Apply all pending changes for a tenant by invalidating the FreeSWITCH XML cache."""
    result = await db.execute(
        select(PendingChange)
        .where(PendingChange.tenant_id == tenant_id, PendingChange.status == "pending")
        .order_by(PendingChange.created_at)
    )
    changes = result.scalars().all()

    if not changes:
        return CommitResult(tenant_id=tenant_id, applied=0, failed=0, errors=[])

    applied = 0
    failed = 0
    errors = []

    esl = await get_esl()
    reload_error = await _apply_change_to_freeswitch(esl)

    for change in changes:
        if reload_error:
            change.status = "failed"
            change.error_message = reload_error
            failed += 1
            errors.append(f"{change.change_type} [{change.entity_id}]: {reload_error}")
            continue

        change.status = "applied"
        change.applied_at = datetime.now(timezone.utc)
        # Mark extension as synced
        if change.entity_id and change.entity_type == "extension":
            ext_result = await db.execute(select(SIPExtension).where(SIPExtension.id == change.entity_id))
            ext = ext_result.scalar_one_or_none()
            if ext:
                ext.freeswitch_synced = True
        applied += 1

    await db.commit()
    return CommitResult(tenant_id=tenant_id, applied=applied, failed=failed, errors=errors)


@router.post("/rollback/{tenant_id}", status_code=status.HTTP_200_OK)
async def rollback_pending(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Discard all pending (unapplied) changes for a tenant."""
    result = await db.execute(
        select(PendingChange)
        .where(PendingChange.tenant_id == tenant_id, PendingChange.status == "pending")
    )
    changes = result.scalars().all()
    count = len(changes)
    for c in changes:
        c.status = "rolled_back"
    await db.commit()
    return {"tenant_id": str(tenant_id), "rolled_back": count}
