import uuid
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any
from jinja2 import Environment, BaseLoader, TemplateError
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.provisioning import PhoneModel, ProvisionedPhone, PhoneButton
from app.models.sip import SIPExtension
from app.models.user import User

router = APIRouter()

# Fernet key derive de SECRET_KEY -- meme pattern que ClientAccess cote ERPCRM,
# pas de variable d'env supplementaire necessaire (TASK-S011.2).
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def _encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except Exception:
        return ""


# ── Phone Models ──────────────────────────────────────────────────────────────

class PhoneModelOut(BaseModel):
    id: uuid.UUID
    brand: str
    model: str
    firmware_version: str | None
    device_type: str
    max_accounts: int
    provisioning_protocol: str
    config_template: str | None
    notes: str | None
    is_active: bool

class PhoneModelCreate(BaseModel):
    brand: str
    model: str
    firmware_version: str | None = None
    device_type: str = "telephone"  # telephone, ata, softphone, intercom
    max_accounts: int = 1
    provisioning_protocol: str = "http"
    config_template: str | None = None
    notes: str | None = None

class PhoneModelUpdate(BaseModel):
    firmware_version: str | None = None
    device_type: str | None = None
    max_accounts: int | None = None
    provisioning_protocol: str | None = None
    config_template: str | None = None
    notes: str | None = None
    is_active: bool | None = None


def _model_out(m: PhoneModel) -> PhoneModelOut:
    return PhoneModelOut(id=m.id, brand=m.brand, model=m.model, firmware_version=m.firmware_version,
                         device_type=m.device_type,
                         max_accounts=m.max_accounts, provisioning_protocol=m.provisioning_protocol,
                         config_template=m.config_template, notes=m.notes, is_active=m.is_active)


@router.get("/models", response_model=list[PhoneModelOut])
async def list_models(db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(PhoneModel).where(PhoneModel.is_active == True).order_by(PhoneModel.brand, PhoneModel.model))
    return [_model_out(m) for m in result.scalars().all()]


@router.post("/models", response_model=PhoneModelOut, status_code=status.HTTP_201_CREATED)
async def create_model(payload: PhoneModelCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    m = PhoneModel(**payload.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return _model_out(m)


@router.put("/models/{model_id}", response_model=PhoneModelOut)
async def update_model(model_id: uuid.UUID, payload: PhoneModelUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(PhoneModel).where(PhoneModel.id == model_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Modèle introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    return _model_out(m)


# ── Provisioned Phones ────────────────────────────────────────────────────────

class PhoneOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    extension_id: uuid.UUID | None
    phone_model_id: uuid.UUID | None
    mac_address: str
    display_name: str | None
    location: str | None
    ip_address: str | None
    firmware_version: str | None
    last_provisioned: datetime | None
    last_seen: datetime | None
    extra_config: dict | None
    is_active: bool
    serial_number: str | None
    hardware_version: str | None
    has_admin_password: bool
    wifi_enabled: bool
    bluetooth_enabled: bool
    headset_used: bool
    expansion_module: str | None
    # Calcule a la volee depuis last_provisioned, pas stocke (TASK-S011.2) -- "jamais" ou
    # "provisionne" (avec la date deja dans last_provisioned). Pas de palier "en retard" :
    # aucun seuil precis n'a ete demande, on n'en invente pas un arbitraire.
    provisioning_status: str

class PhoneAdminPasswordOut(PhoneOut):
    admin_password: str | None = None

class PhoneCreate(BaseModel):
    extension_id: uuid.UUID | None = None
    phone_model_id: uuid.UUID | None = None
    mac_address: str
    display_name: str | None = None
    location: str | None = None
    extra_config: dict | None = None
    serial_number: str | None = None
    hardware_version: str | None = None
    admin_password: str | None = None
    wifi_enabled: bool = False
    bluetooth_enabled: bool = False
    headset_used: bool = False
    expansion_module: str | None = None

class PhoneUpdate(BaseModel):
    extension_id: uuid.UUID | None = None
    phone_model_id: uuid.UUID | None = None
    display_name: str | None = None
    location: str | None = None
    ip_address: str | None = None
    firmware_version: str | None = None
    extra_config: dict | None = None
    is_active: bool | None = None
    serial_number: str | None = None
    hardware_version: str | None = None
    admin_password: str | None = None
    wifi_enabled: bool | None = None
    bluetooth_enabled: bool | None = None
    headset_used: bool | None = None
    expansion_module: str | None = None
    mac_address: str | None = None  # remplacement d'appareil physique : seul le MAC/SN change


def _phone_out(p: ProvisionedPhone, reveal: bool = False) -> PhoneOut:
    base = dict(
        id=p.id, tenant_id=p.tenant_id, extension_id=p.extension_id,
        phone_model_id=p.phone_model_id, mac_address=p.mac_address,
        display_name=p.display_name, location=p.location, ip_address=p.ip_address,
        firmware_version=p.firmware_version, last_provisioned=p.last_provisioned,
        last_seen=p.last_seen, extra_config=p.extra_config, is_active=p.is_active,
        serial_number=p.serial_number, hardware_version=p.hardware_version,
        has_admin_password=bool(p.encrypted_admin_password),
        wifi_enabled=p.wifi_enabled, bluetooth_enabled=p.bluetooth_enabled,
        headset_used=p.headset_used, expansion_module=p.expansion_module,
        provisioning_status="provisionne" if p.last_provisioned else "jamais",
    )
    if reveal:
        return PhoneAdminPasswordOut(**base, admin_password=_decrypt(p.encrypted_admin_password) if p.encrypted_admin_password else None)
    return PhoneOut(**base)


@router.get("/tenant/{tenant_id}", response_model=list[PhoneOut])
async def list_phones(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.tenant_id == tenant_id).order_by(ProvisionedPhone.mac_address))
    return [_phone_out(p) for p in result.scalars().all()]


@router.get("/by-extension/{extension_id}", response_model=PhoneOut | None)
async def get_phone_by_extension(extension_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """
    Téléphone physique attribué à ce poste (TASK-023.19) -- appelé par ERPCRM (proxy)
    pour afficher/gérer l'appareil depuis la fiche contact. Retourne null si aucun
    appareil n'est encore attribué (pas une erreur).
    """
    result = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.extension_id == extension_id))
    phone = result.scalar_one_or_none()
    return _phone_out(phone) if phone else None


@router.post("/tenant/{tenant_id}", response_model=PhoneOut, status_code=status.HTTP_201_CREATED)
async def create_phone(tenant_id: uuid.UUID, payload: PhoneCreate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    mac = payload.mac_address.upper().replace('-', ':')
    existing = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.mac_address == mac))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="MAC address déjà enregistrée")
    data = payload.model_dump()
    data['mac_address'] = mac
    admin_password = data.pop('admin_password', None)
    p = ProvisionedPhone(tenant_id=tenant_id, **data)
    if admin_password:
        p.encrypted_admin_password = _encrypt(admin_password)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _phone_out(p)


@router.put("/{phone_id}", response_model=PhoneOut)
async def update_phone(phone_id: uuid.UUID, payload: PhoneUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.id == phone_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    data = payload.model_dump(exclude_unset=True)
    admin_password_set = 'admin_password' in data
    admin_password = data.pop('admin_password', None)
    if 'mac_address' in data and data['mac_address']:
        data['mac_address'] = data['mac_address'].upper().replace('-', ':')
    for k, v in data.items():
        setattr(p, k, v)
    if admin_password_set:
        p.encrypted_admin_password = _encrypt(admin_password) if admin_password else None
    await db.commit()
    await db.refresh(p)
    return _phone_out(p)


@router.get("/{phone_id}/reveal-admin-password", response_model=PhoneAdminPasswordOut)
async def reveal_admin_password(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.id == phone_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    return _phone_out(p, reveal=True)


@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.id == phone_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    await db.delete(p)
    await db.commit()


@router.get("/{phone_id}/config", response_class=PlainTextResponse)
async def get_phone_config(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns rendered provisioning config for the phone. No auth — phones fetch this directly."""
    result = await db.execute(
        select(ProvisionedPhone).where(ProvisionedPhone.id == phone_id)
    )
    phone = result.scalar_one_or_none()
    if not phone or not phone.is_active:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")

    template_text = None
    if phone.phone_model_id:
        m = await db.execute(select(PhoneModel).where(PhoneModel.id == phone.phone_model_id))
        model = m.scalar_one_or_none()
        if model:
            template_text = model.config_template

    if not template_text:
        raise HTTPException(status_code=404, detail="Aucun template de config pour ce modèle")

    ext = None
    if phone.extension_id:
        e = await db.execute(select(SIPExtension).where(SIPExtension.id == phone.extension_id))
        ext = e.scalar_one_or_none()

    context: dict[str, Any] = {
        "phone": phone,
        "extension": ext,
        "mac": phone.mac_address.replace(":", "").lower(),
    }
    if phone.extra_config:
        context.update(phone.extra_config)

    try:
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(template_text)
        rendered = tmpl.render(**context)
    except TemplateError as e:
        raise HTTPException(status_code=500, detail=f"Erreur template: {e}")

    # Update last_provisioned
    phone.last_provisioned = datetime.now(timezone.utc)
    await db.commit()

    return rendered


@router.get("/mac/{mac_address}/config", response_class=PlainTextResponse)
async def get_phone_config_by_mac(mac_address: str, db: AsyncSession = Depends(get_db)):
    """Provisioning URL by MAC (phones POST their MAC on boot)."""
    mac = mac_address.upper().replace('-', ':')
    result = await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.mac_address == mac))
    phone = result.scalar_one_or_none()
    if not phone:
        raise HTTPException(status_code=404, detail="MAC non enregistrée")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/api/v1/provisioning/{phone.id}/config")


# ── Boutons/touches programmables (TASK-023.17) ────────────────────────────────
# Editeur en LISTE -- decouple de TASK-S011.3 (mapping visuel sur photo, bloque
# faute de photo). Memes donnees, accessibles sans attendre une image cliquable.

class PhoneButtonOut(BaseModel):
    id: uuid.UUID
    provisioned_phone_id: uuid.UUID
    position: int
    page: int
    button_type: str
    label: str | None
    value: str | None
    destination: str | None
    sip_account_index: int
    client_editable: bool
    locked_by_simpleip: bool

class PhoneButtonCreate(BaseModel):
    position: int
    page: int = 0
    button_type: str
    label: str | None = None
    value: str | None = None
    destination: str | None = None
    sip_account_index: int = 1
    client_editable: bool = False
    locked_by_simpleip: bool = True

class PhoneButtonUpdate(BaseModel):
    position: int | None = None
    page: int | None = None
    button_type: str | None = None
    label: str | None = None
    value: str | None = None
    destination: str | None = None
    sip_account_index: int | None = None
    client_editable: bool | None = None
    locked_by_simpleip: bool | None = None


def _button_out(b: PhoneButton) -> PhoneButtonOut:
    return PhoneButtonOut(
        id=b.id, provisioned_phone_id=b.provisioned_phone_id, position=b.position, page=b.page,
        button_type=b.button_type, label=b.label, value=b.value, destination=b.destination,
        sip_account_index=b.sip_account_index, client_editable=b.client_editable,
        locked_by_simpleip=b.locked_by_simpleip,
    )


@router.get("/{phone_id}/buttons", response_model=list[PhoneButtonOut])
async def list_phone_buttons(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(
        select(PhoneButton).where(PhoneButton.provisioned_phone_id == phone_id).order_by(PhoneButton.page, PhoneButton.position)
    )
    return [_button_out(b) for b in result.scalars().all()]


@router.post("/{phone_id}/buttons", response_model=PhoneButtonOut, status_code=status.HTTP_201_CREATED)
async def create_phone_button(phone_id: uuid.UUID, payload: PhoneButtonCreate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    b = PhoneButton(provisioned_phone_id=phone_id, **payload.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return _button_out(b)


@router.put("/buttons/{button_id}", response_model=PhoneButtonOut)
async def update_phone_button(button_id: uuid.UUID, payload: PhoneButtonUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(PhoneButton).where(PhoneButton.id == button_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Bouton introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    await db.commit()
    await db.refresh(b)
    return _button_out(b)


@router.delete("/buttons/{button_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_button(button_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(PhoneButton).where(PhoneButton.id == button_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Bouton introuvable")
    await db.delete(b)
    await db.commit()
