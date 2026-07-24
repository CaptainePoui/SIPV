"""
Audit logging — enregistre chaque modification avec avant/après, utilisateur et IP.
Appeler AVANT db.commit() car cette fonction ne commit pas elle-même.
"""
import uuid
from typing import Any
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def log_audit(
    db: AsyncSession,
    *,
    request: Request,
    user: User | None,
    entity_type: str,
    action: str,                          # "create" | "update" | "delete"
    old_data: dict[str, Any] | None,
    new_data: dict[str, Any] | None,
    entity_id: str | None = None,
    entity_label: str | None = None,
    tenant_id: uuid.UUID | None = None,
) -> None:
    entry = AuditLog(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        action=action,
        old_data=old_data,
        new_data=new_data,
        changed_by=user.email if user else "erpcrm-proxy",
        changed_by_ip=get_client_ip(request),
    )
    db.add(entry)
