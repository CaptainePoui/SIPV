"""
Synchronization from ERPCRM to SIPV.
ERPCRM pushes company data (account_number, name) to create/update tenants.
"""
import logging
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.core.did_route_sync import sync_inbound_route_from_did
from app.core import erpcrm_client
from app.models.tenant import Tenant
from app.models.sip import SIPExtension, TenantDID
from app.models.e911 import E911Address

logger = logging.getLogger("sync")

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


class ERPCRMSiteSync(BaseModel):
    erpcrm_site_id: uuid.UUID
    tenant_id: uuid.UUID
    label: str
    civic_number: str
    street_name: str
    unit: str | None = None
    city: str
    province: str
    postal_code: str
    country: str = "CA"
    is_active: bool = True


class SiteSyncResult(BaseModel):
    action: str  # created, updated
    e911_address_id: str


@router.post("/site", response_model=SiteSyncResult)
async def sync_site(payload: ERPCRMSiteSync, db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """Cree ou met a jour la copie SIPV d'une succursale (E911Address) -- ERPCRM
    est maitre pour company_sites, cette copie sert uniquement aux assignations
    911 (DID911Assignment/ExtensionE911Assignment) cote SIPV. Retrouvee par
    erpcrm_site_id, jamais par label (peut changer)."""
    result = await db.execute(select(E911Address).where(E911Address.erpcrm_site_id == payload.erpcrm_site_id))
    addr = result.scalar_one_or_none()

    if not addr:
        addr = E911Address(
            tenant_id=payload.tenant_id, erpcrm_site_id=payload.erpcrm_site_id,
            label=payload.label, civic_number=payload.civic_number, street_name=payload.street_name,
            unit=payload.unit, city=payload.city, province=payload.province,
            postal_code=payload.postal_code, country=payload.country, is_active=payload.is_active,
        )
        db.add(addr)
        await db.commit()
        await db.refresh(addr)
        return SiteSyncResult(action="created", e911_address_id=str(addr.id))

    addr.label = payload.label
    addr.civic_number = payload.civic_number
    addr.street_name = payload.street_name
    addr.unit = payload.unit
    addr.city = payload.city
    addr.province = payload.province
    addr.postal_code = payload.postal_code
    addr.country = payload.country
    addr.is_active = payload.is_active
    addr.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return SiteSyncResult(action="updated", e911_address_id=str(addr.id))


class ERPCRMDidSync(BaseModel):
    erpcrm_did_id: uuid.UUID
    tenant_id: uuid.UUID
    number: str
    label: str | None = None
    destination_type: str | None = None
    destination: str | None = None
    after_message_destination_type: str | None = None
    after_message_destination: str | None = None
    is_active: bool = True
    schedule_id: uuid.UUID | None = None


class DidSyncResult(BaseModel):
    action: str  # created, updated, adopted
    tenant_did_id: str


@router.post("/did", response_model=DidSyncResult)
async def sync_did(payload: ERPCRMDidSync, db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """Cree ou met a jour la copie SIPV (TenantDID) d'un DID ERPCRM -- ERPCRM
    est maitre (numero, destination, succursale via l'app), SIPV reste la
    source reelle du routage d'appel. Retrouve par erpcrm_did_id ; si absent,
    adopte un TenantDID existant avec le meme numero (cree via SIPV avant
    cette synchronisation) plutot que d'echouer sur la contrainte unique."""
    result = await db.execute(select(TenantDID).where(TenantDID.erpcrm_did_id == payload.erpcrm_did_id))
    did = result.scalar_one_or_none()
    action = "updated"

    if not did:
        result = await db.execute(select(TenantDID).where(TenantDID.number == payload.number))
        did = result.scalar_one_or_none()
        if did:
            action = "adopted"

    dtype = payload.destination_type or "extension"

    if not did:
        did = TenantDID(
            tenant_id=payload.tenant_id, erpcrm_did_id=payload.erpcrm_did_id, number=payload.number,
            label=payload.label, destination_type=dtype, destination=payload.destination,
            after_message_destination_type=payload.after_message_destination_type,
            after_message_destination=payload.after_message_destination,
            is_active=payload.is_active, schedule_id=payload.schedule_id,
        )
        db.add(did)
        await db.flush()
        await sync_inbound_route_from_did(did, db)
        await db.commit()
        await db.refresh(did)
        # TASK-021/S032 : notifie ERPCRM pour la facturation recurrente -- seulement
        # a la vraie creation (pas update/adopted), best-effort, ne bloque jamais
        # le sync. C'est ICI que les DID sont reellement crees en pratique (ERPCRM
        # est maitre, /did est le chemin normal -- dids.py::create_did existe mais
        # est le chemin natif SIPV, rarement utilise pour de vrais DID).
        try:
            await erpcrm_client.send_billing_event(
                tenant_id=str(did.tenant_id), action="did_added", service_type="did",
                service_ref=str(did.id), description=f"DID {did.number}" + (f" — {did.label}" if did.label else ""),
            )
        except httpx.HTTPError as e:
            logger.warning("Notification facturation ERPCRM echouee pour DID %s: %s", did.id, e)
        return DidSyncResult(action="created", tenant_did_id=str(did.id))

    did.erpcrm_did_id = payload.erpcrm_did_id
    did.tenant_id = payload.tenant_id
    did.label = payload.label
    did.destination_type = dtype
    did.destination = payload.destination
    did.after_message_destination_type = payload.after_message_destination_type
    did.after_message_destination = payload.after_message_destination
    did.is_active = payload.is_active
    did.schedule_id = payload.schedule_id
    await sync_inbound_route_from_did(did, db)
    await db.commit()
    return DidSyncResult(action=action, tenant_did_id=str(did.id))


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """Health check for ERPCRM to verify SIPV connection."""
    result = await db.execute(select(Tenant))
    count = len(result.scalars().all())
    return {"status": "ok", "tenant_count": count, "project": "SIPV"}


class ERPCRMEvent(BaseModel):
    action: str  # contact_name_changed
    erpcrm_contact_id: uuid.UUID
    data: dict = {}


@router.post("/erpcrm-event")
async def erpcrm_event(payload: ERPCRMEvent, db: AsyncSession = Depends(get_db), _: str = Depends(verify_api_key)):
    """
    Appele par ERPCRM quand un contact lie a une extension change (TASK-S022).
    Symetrique de POST /api/v1/sipv/event cote ERPCRM.
    """
    result = await db.execute(select(SIPExtension).where(SIPExtension.erpcrm_contact_id == payload.erpcrm_contact_id))
    extensions = result.scalars().all()
    if not extensions:
        raise HTTPException(status_code=404, detail="Aucune extension liee a ce contact")

    if payload.action != "contact_name_changed":
        raise HTTPException(status_code=400, detail=f"Action inconnue : {payload.action}")

    updated = []
    for ext in extensions:
        first = payload.data.get("first_name")
        last = payload.data.get("last_name")
        full_name = f"{first or ''} {last or ''}".strip()
        if full_name:
            ext.caller_id_name = full_name
            # TASK-023.14 : "autre" -- le poste peut avoir un nom different de celui
            # du contact ERPCRM lie ; name_override=True protege `name` de ce sync.
            if not ext.name_override:
                ext.name = full_name
        ext.freeswitch_synced = False
        updated.append(ext.username)

    await db.commit()
    return {"status": "ok", "updated_extensions": updated}
