"""Appareils internes (TASK-027.3, 2026-10-11) : ERPCRM, Serveur -> onglet « Appareils internes ».

Philippe : « on choisit le tenant d'abord, ca nous amene a une liste de postes deja configures dans le tenant et on a juste
a cocher les postes a l'interne ; on peut meme ajouter plusieurs tenants au cas ou plusieurs entreprises sur le meme
Internet auraient un SIPV ». Un poste coche « Interne » recoit l'adresse interne de son serveur comme proxy SIP (P48) a
sa prochaine configuration ; tous les autres gardent l'adresse publique (0069). Source unique ici (ERPCRM ne garde rien).
"""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user_or_service
from app.core.config import settings
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.provisioning import PhoneModel, ProvisionedPhone
from app.models.server import InternalNetworkTenant, SipvServer
from app.models.sip import SIPExtension
from app.models.tenant import Tenant
from app.models.user import User

log = logging.getLogger("internal_devices")
router = APIRouter()


def internal_address(server: SipvServer | None) -> str:
    """Adresse du serveur sur le reseau du bureau (celle de sa fiche, sinon SIPV_HOST)."""
    return (server.ip_address if server and server.ip_address else None) or settings.SIPV_HOST


async def _server(db: AsyncSession, server_id: uuid.UUID) -> SipvServer:
    s = await db.get(SipvServer, server_id)
    if not s:
        raise HTTPException(status_code=404, detail="Serveur introuvable")
    return s


async def _tenant_on(db: AsyncSession, server: SipvServer, tenant_id: uuid.UUID) -> Tenant:
    t = await db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    if t.server_id != server.id:
        raise HTTPException(status_code=422, detail=f"{t.account_number} n'est pas hébergé sur {server.name}")
    return t


def _audit(db, request: Request, user, tenant: Tenant, label: str, old, new):
    db.add(AuditLog(tenant_id=tenant.id, entity_type="internal_devices", entity_id=str(tenant.id), entity_label=label,
                    action="update", old_data=old, new_data=new, changed_by=user.email if user else "ERPCRM",
                    changed_by_ip=request.client.host if request.client else "?"))


@router.get("/server/{server_id}")
async def list_internal(server_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        _: User | None = Depends(get_current_user_or_service)):
    """Tenants affiches (ajoutes, ou qui ont un poste coche) avec tous leurs postes ; les autres tenants du serveur."""
    server = await _server(db, server_id)
    tenants = (await db.execute(select(Tenant).where(Tenant.server_id == server.id).order_by(Tenant.account_number))).scalars().all()
    listed = {r.tenant_id for r in (await db.execute(select(InternalNetworkTenant).where(InternalNetworkTenant.server_id == server.id))).scalars().all()}
    exts = (await db.execute(select(SIPExtension).where(SIPExtension.tenant_id.in_([t.id for t in tenants]))
                             .order_by(SIPExtension.extension))).scalars().all()
    listed |= {e.tenant_id for e in exts if e.internal_network}
    phones = {p.extension_id: p for p in (await db.execute(select(ProvisionedPhone).where(
        ProvisionedPhone.extension_id.in_([e.id for e in exts]), ProvisionedPhone.is_active == True))).scalars().all()}
    models = {m.id: m for m in (await db.execute(select(PhoneModel))).scalars().all()}
    try:
        from app.core.phone_reboot import registered_users
        online = await registered_users()
    except Exception as ex:                       # FreeSWITCH injoignable : la liste reste utilisable
        log.warning("enregistrements non lus : %s", ex)
        online = None

    def phone(e):
        p = phones.get(e.id)
        if not p:
            return None
        m = models.get(p.phone_model_id)
        return {"mac": p.mac_address, "model": f"{m.brand} {m.model}" if m else None}

    out = []
    for t in tenants:
        if t.id not in listed:
            continue
        out.append({"id": str(t.id), "account_number": t.account_number, "company_name": t.company_name,
                    "erpcrm_company_id": t.erpcrm_company_id,
                    "extensions": [{"id": str(e.id), "extension": e.extension, "name": e.name, "username": e.username,
                                    "is_active": e.is_active, "internal": e.internal_network, "phone": phone(e),
                                    "registered": (e.username in online) if online is not None else None}
                                   for e in exts if e.tenant_id == t.id]})
    return {"server": {"id": str(server.id), "name": server.name, "internal_address": internal_address(server),
                       "public_address": settings.SIPV_PUBLIC_IP},
            "tenants": out,
            "other_tenants": [{"id": str(t.id), "account_number": t.account_number, "company_name": t.company_name}
                              for t in tenants if t.id not in listed]}


@router.post("/server/{server_id}/tenants/{tenant_id}")
async def add_tenant(server_id: uuid.UUID, tenant_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                     user: User | None = Depends(get_current_user_or_service)):
    server = await _server(db, server_id)
    t = await _tenant_on(db, server, tenant_id)
    exists = (await db.execute(select(InternalNetworkTenant).where(InternalNetworkTenant.server_id == server.id,
                                                                   InternalNetworkTenant.tenant_id == t.id))).scalar_one_or_none()
    if not exists:
        db.add(InternalNetworkTenant(server_id=server.id, tenant_id=t.id))
        _audit(db, request, user, t, f"Appareils internes : {t.account_number} ajouté", None, {"tenant": t.account_number})
        await db.commit()
    return {"ok": True}


@router.delete("/server/{server_id}/tenants/{tenant_id}")
async def remove_tenant(server_id: uuid.UUID, tenant_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                        user: User | None = Depends(get_current_user_or_service)):
    """Retire le tenant de l'onglet : ses postes coches redeviennent externes."""
    server = await _server(db, server_id)
    t = await _tenant_on(db, server, tenant_id)
    was = (await db.execute(select(SIPExtension.extension).where(SIPExtension.tenant_id == t.id,
                                                                 SIPExtension.internal_network == True))).scalars().all()
    await db.execute(update(SIPExtension).where(SIPExtension.tenant_id == t.id).values(internal_network=False))
    row = (await db.execute(select(InternalNetworkTenant).where(InternalNetworkTenant.server_id == server.id,
                                                                InternalNetworkTenant.tenant_id == t.id))).scalar_one_or_none()
    if row:
        await db.delete(row)
    _audit(db, request, user, t, f"Appareils internes : {t.account_number} retiré", {"internes": list(was)}, {"internes": []})
    await db.commit()
    return {"ok": True, "unchecked": list(was)}


class InternalIn(BaseModel):
    internal: bool


@router.put("/extensions/{extension_id}")
async def set_internal(extension_id: uuid.UUID, payload: InternalIn, request: Request, db: AsyncSession = Depends(get_db),
                       user: User | None = Depends(get_current_user_or_service)):
    e = await db.get(SIPExtension, extension_id)
    if not e:
        raise HTTPException(status_code=404, detail="Poste introuvable")
    t = await db.get(Tenant, e.tenant_id)
    if not t or not t.server_id:
        raise HTTPException(status_code=422, detail="Ce poste n'est sur aucun serveur")
    if e.internal_network != payload.internal:
        e.internal_network = payload.internal
        _audit(db, request, user, t, f"Poste {e.extension} : {'interne' if payload.internal else 'externe'}",
               {"poste": e.extension, "interne": not payload.internal}, {"poste": e.extension, "interne": payload.internal})
        if payload.internal:                      # le tenant reste affiche meme si on decoche ensuite tous ses postes
            listed = (await db.execute(select(InternalNetworkTenant).where(InternalNetworkTenant.server_id == t.server_id,
                                                                           InternalNetworkTenant.tenant_id == t.id))).scalar_one_or_none()
            if not listed:
                db.add(InternalNetworkTenant(server_id=t.server_id, tenant_id=t.id))
        await db.commit()
    return {"id": str(e.id), "internal": e.internal_network}
