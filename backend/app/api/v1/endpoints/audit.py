"""
Audit log — historique complet des modifications (admin Simple IP uniquement).
"""
import uuid
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter()


class AuditLogOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    entity_type: str
    entity_id: str | None
    entity_label: str | None
    action: str
    old_data: dict[str, Any] | None
    new_data: dict[str, Any] | None
    changed_by: str
    changed_by_ip: str
    created_at: datetime


def _out(a: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=a.id,
        tenant_id=a.tenant_id,
        entity_type=a.entity_type,
        entity_id=a.entity_id,
        entity_label=a.entity_label,
        action=a.action,
        old_data=a.old_data,
        new_data=a.new_data,
        changed_by=a.changed_by,
        changed_by_ip=a.changed_by_ip,
        created_at=a.created_at,
    )


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    tenant_id: uuid.UUID | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    changed_by: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Historique des modifications. Filtres optionnels :
    - tenant_id, entity_type, action (create/update/delete)
    - changed_by (email partiel ou exact)
    - date_from / date_to
    """
    filters = []
    if tenant_id:
        filters.append(AuditLog.tenant_id == tenant_id)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if action:
        filters.append(AuditLog.action == action)
    if changed_by:
        filters.append(AuditLog.changed_by.ilike(f"%{changed_by}%"))
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)

    q = (
        select(AuditLog)
        .where(and_(*filters) if filters else True)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(q)
    return [_out(a) for a in result.scalars().all()]


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogOut])
async def entity_history(
    entity_type: str,
    entity_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Historique complet d'un objet spécifique (ex: une extension)."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return [_out(a) for a in result.scalars().all()]
