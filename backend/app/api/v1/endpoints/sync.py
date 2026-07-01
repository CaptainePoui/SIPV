"""
Synchronization from ERPCRM to SIPV.
ERPCRM pushes company data (account_number, name) to create/update tenants.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.models.tenant import Tenant

router = APIRouter()


def verify_api_key(x_api_key: str = Header(...)):
    if not settings.ERPCRM_API_KEY or x_api_key != settings.ERPCRM_API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return x_api_key


class ERPCRMCompanySync(BaseModel):
    account_number: str
    company_name: str
    erpcrm_company_id: str
    is_active: bool = True


class SyncResult(BaseModel):
    action: str  # created, updated, no_change
    tenant_id: str
    account_number: str
    company_name: str


@router.post("/company", response_model=SyncResult)
async def sync_company(payload: ERPCRMCompanySync, db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """Called by ERPCRM when a company is created/updated."""
    result = await db.execute(select(Tenant).where(Tenant.account_number == payload.account_number))
    tenant = result.scalar_one_or_none()

    if not tenant:
        context_prefix = f"t-{payload.account_number.lower().replace(' ', '_').replace('-', '_')}"
        tenant = Tenant(
            account_number=payload.account_number,
            company_name=payload.company_name,
            erpcrm_company_id=payload.erpcrm_company_id,
            is_active=payload.is_active,
            context_prefix=context_prefix,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return SyncResult(action="created", tenant_id=str(tenant.id), account_number=tenant.account_number, company_name=tenant.company_name)

    changed = False
    if tenant.company_name != payload.company_name:
        tenant.company_name = payload.company_name
        changed = True
    if tenant.is_active != payload.is_active:
        tenant.is_active = payload.is_active
        changed = True
    if tenant.erpcrm_company_id != payload.erpcrm_company_id:
        tenant.erpcrm_company_id = payload.erpcrm_company_id
        changed = True

    if changed:
        tenant.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return SyncResult(action="updated", tenant_id=str(tenant.id), account_number=tenant.account_number, company_name=tenant.company_name)

    return SyncResult(action="no_change", tenant_id=str(tenant.id), account_number=tenant.account_number, company_name=tenant.company_name)


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """Health check for ERPCRM to verify SIPV connection."""
    result = await db.execute(select(Tenant))
    count = len(result.scalars().all())
    return {"status": "ok", "tenant_count": count, "project": "SIPV"}
