"""Gestion des serveurs SIPV (TASK-S042) -- fondation multi-serveur, pas encore
le dispatcheur central ("classe 4") lui-meme, juste le catalogue des serveurs
et le lien Tenant -> serveur hebergeur."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.server import SipvServer
from app.models.provisioning import GlobalTemplate, TenantTemplate
from app.models.user import User

router = APIRouter()


class ServerOut(BaseModel):
    id: uuid.UUID
    name: str
    hostname: str
    ip_address: str | None
    sip_inbound_ip: str | None
    sip_outbound_ip: str | None
    is_active: bool
    notes: str | None
    created_at: datetime
    tenant_count: int = 0

    model_config = {"from_attributes": True}


class ServerCreate(BaseModel):
    name: str
    hostname: str
    ip_address: str | None = None
    sip_inbound_ip: str | None = None
    sip_outbound_ip: str | None = None
    notes: str | None = None


class ServerUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    sip_inbound_ip: str | None = None
    sip_outbound_ip: str | None = None
    is_active: bool | None = None
    notes: str | None = None


def _out(s: SipvServer, tenant_count: int) -> ServerOut:
    return ServerOut(
        id=s.id, name=s.name, hostname=s.hostname, ip_address=s.ip_address,
        sip_inbound_ip=s.sip_inbound_ip, sip_outbound_ip=s.sip_outbound_ip,
        is_active=s.is_active, notes=s.notes, created_at=s.created_at,
        tenant_count=tenant_count,
    )


@router.get("", response_model=list[ServerOut])
async def list_servers(db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    from app.models.tenant import Tenant
    result = await db.execute(select(SipvServer).order_by(SipvServer.name))
    servers = result.scalars().all()
    out = []
    for s in servers:
        count = (await db.execute(select(Tenant).where(Tenant.server_id == s.id))).scalars().all()
        out.append(_out(s, len(count)))
    return out


@router.post("", response_model=ServerOut, status_code=status.HTTP_201_CREATED)
async def create_server(payload: ServerCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    existing = await db.execute(select(SipvServer).where(SipvServer.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom de serveur déjà utilisé")
    s = SipvServer(**payload.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _out(s, 0)


@router.put("/{server_id}", response_model=ServerOut)
async def update_server(server_id: uuid.UUID, payload: ServerUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    from app.models.tenant import Tenant
    s = await db.get(SipvServer, server_id)
    if not s:
        raise HTTPException(status_code=404, detail="Serveur introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    count = (await db.execute(select(Tenant).where(Tenant.server_id == s.id))).scalars().all()
    return _out(s, len(count))


# ── Global Templates -- chaine d'heritage a 5 niveaux (TASK-S044) ──────────────
class GlobalTemplateOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    description: str | None
    options: dict
    is_default: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class GlobalTemplateCreate(BaseModel):
    server_id: uuid.UUID
    name: str
    description: str | None = None
    options: dict = {}
    is_default: bool = False
    is_active: bool = True


class GlobalTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    options: dict | None = None
    is_default: bool | None = None
    is_active: bool | None = None


@router.get("/{server_id}/global-templates", response_model=list[GlobalTemplateOut])
async def list_global_templates(server_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(GlobalTemplate).where(GlobalTemplate.server_id == server_id).order_by(GlobalTemplate.name))
    return result.scalars().all()


@router.post("/global-templates", response_model=GlobalTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_global_template(payload: GlobalTemplateCreate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    if payload.is_default:
        await db.execute(update(GlobalTemplate).where(GlobalTemplate.server_id == payload.server_id).values(is_default=False))
    t = GlobalTemplate(**payload.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@router.put("/global-templates/{template_id}", response_model=GlobalTemplateOut)
async def update_global_template(template_id: uuid.UUID, payload: GlobalTemplateUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await db.get(GlobalTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    if payload.is_default:
        await db.execute(update(GlobalTemplate).where(GlobalTemplate.server_id == t.server_id, GlobalTemplate.id != t.id).values(is_default=False))
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return t


@router.delete("/global-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_global_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await db.get(GlobalTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    await db.delete(t)
    await db.commit()


# ── Tenant Templates -- bibliotheque par serveur, choisie explicitement par
# compagnie (TASK-S044.1) -- meme forme que Global Templates, mais JAMAIS
# appliquee automatiquement (voir Tenant.selected_tenant_template_id).
class TenantTemplateOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    description: str | None
    options: dict
    is_default: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TenantTemplateCreate(BaseModel):
    server_id: uuid.UUID
    name: str
    description: str | None = None
    options: dict = {}
    is_default: bool = False
    is_active: bool = True


class TenantTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    options: dict | None = None
    is_default: bool | None = None
    is_active: bool | None = None


@router.get("/{server_id}/tenant-templates", response_model=list[TenantTemplateOut])
async def list_tenant_templates(server_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(TenantTemplate).where(TenantTemplate.server_id == server_id).order_by(TenantTemplate.name))
    return result.scalars().all()


@router.post("/tenant-templates", response_model=TenantTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_tenant_template(payload: TenantTemplateCreate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    if payload.is_default:
        await db.execute(update(TenantTemplate).where(TenantTemplate.server_id == payload.server_id).values(is_default=False))
    t = TenantTemplate(**payload.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@router.put("/tenant-templates/{template_id}", response_model=TenantTemplateOut)
async def update_tenant_template(template_id: uuid.UUID, payload: TenantTemplateUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await db.get(TenantTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    if payload.is_default:
        await db.execute(update(TenantTemplate).where(TenantTemplate.server_id == t.server_id, TenantTemplate.id != t.id).values(is_default=False))
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return t


@router.delete("/tenant-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await db.get(TenantTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    await db.delete(t)
    await db.commit()
