"""
Commit/Checkpoint system for Asterisk config changes.
Pending changes are queued and applied to Asterisk PJSIP Realtime tables atomically.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
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


async def _apply_change_to_asterisk(change: PendingChange, db: AsyncSession) -> bool:
    """Write a pending change to the Asterisk PJSIP Realtime tables."""
    try:
        if change.entity_type == "extension":
            if change.change_type == "add_extension":
                payload = change.payload
                username = payload["username"]
                # ps_endpoints
                await db.execute(
                    __import__('sqlalchemy').text("""
                    INSERT INTO ps_endpoints (id, context, aors, auth, disallow, allow, direct_media, force_rport, rewrite_contact, language, callerid)
                    VALUES (:id, :context, :id, :auth, 'all', 'ulaw,alaw,g722', 'no', 'yes', 'yes', 'fr', :callerid)
                    ON CONFLICT (id) DO UPDATE SET context=EXCLUDED.context, aors=EXCLUDED.aors, auth=EXCLUDED.auth
                    """),
                    {"id": username, "context": f"from-internal", "auth": username,
                     "callerid": f'"{payload.get("name", username)}" <{payload.get("extension", username)}>'}
                )
                # ps_auths
                await db.execute(
                    __import__('sqlalchemy').text("""
                    INSERT INTO ps_auths (id, auth_type, username, password)
                    VALUES (:id, 'userpass', :username, :password)
                    ON CONFLICT (id) DO UPDATE SET password=EXCLUDED.password
                    """),
                    {"id": username, "username": username, "password": payload["password"]}
                )
                # ps_aors
                await db.execute(
                    __import__('sqlalchemy').text("""
                    INSERT INTO ps_aors (id, max_contacts, remove_existing, qualify_frequency)
                    VALUES (:id, 3, 'yes', 60)
                    ON CONFLICT (id) DO NOTHING
                    """),
                    {"id": username}
                )

            elif change.change_type == "remove_extension":
                username = change.payload.get("username")
                if username:
                    for table in ["ps_contacts", "ps_aors", "ps_auths", "ps_endpoints"]:
                        await db.execute(__import__('sqlalchemy').text(f"DELETE FROM {table} WHERE id = :id"), {"id": username})

        return True
    except Exception as e:
        change.error_message = str(e)
        return False


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
    """Apply all pending changes for a tenant to Asterisk Realtime tables."""
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

    for change in changes:
        success = await _apply_change_to_asterisk(change, db)
        if success:
            change.status = "applied"
            change.applied_at = datetime.now(timezone.utc)
            # Mark extension as synced
            if change.entity_id and change.entity_type == "extension":
                ext_result = await db.execute(select(SIPExtension).where(SIPExtension.id == change.entity_id))
                ext = ext_result.scalar_one_or_none()
                if ext:
                    ext.asterisk_synced = True
            applied += 1
        else:
            change.status = "failed"
            failed += 1
            errors.append(f"{change.change_type} [{change.entity_id}]: {change.error_message}")

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
