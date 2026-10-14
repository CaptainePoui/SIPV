import re
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any
from jinja2 import Environment, BaseLoader, TemplateError
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.provisioning import PhoneModel, ProvisionedPhone, PhoneButton, PhoneButtonTemplate, PhoneButtonTemplateItem, GlobalTemplate, TenantTemplate, TenantModelTemplate
from app.models.sip import SIPExtension
from app.models.tenant import Tenant
from app.models.server import SipvServer
from app.models.user import User

from app.api.v1.endpoints.internal_devices import internal_address
from app.core.gs_catalog import option_catalog, to_pcodes, managed_in, MANAGED
from app.core.grandstream_keys import vpk_keys, merge_keys, key_catalog, softkey_items, normalize_layouts, GS_KEY_MODES

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
    provisioning_protocol: str
    selected_tenant_model_template_ids: list[uuid.UUID] = []  # TASK-S044.2
    button_template_id: uuid.UUID | None = None               # modele de provisionnement choisi (TASK-051)
    softkeys: dict | None = None                              # boutons sous l'ecran personnalises (0075)
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
    provisioning_protocol: str = "https"

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
    provisioning_protocol: str | None = None
    mac_address: str | None = None  # remplacement d'appareil physique : seul le MAC/SN change
    selected_tenant_model_template_ids: list[uuid.UUID] | None = None  # TASK-S044.2


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
        provisioning_protocol=p.provisioning_protocol,
        selected_tenant_model_template_ids=p.selected_tenant_model_template_ids or [],
        button_template_id=p.button_template_id,
        softkeys={"layouts": normalize_layouts((p.softkeys or {}).get("layouts"))} if p.softkeys else None,
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


# Defauts systeme du catalogue d'options telephonie (TASK-S011.5) -- utilises quand
# ni la compagnie (Tenant.phone_option_defaults) ni le poste (ProvisionedPhone.extra_config)
# ne precisent une valeur. Catalogue volontairement minimal (GXP2135 seulement pour
# l'instant) -- voir ref_data.py cote ERPCRM pour la liste affichee a l'utilisateur.
PHONE_OPTION_SYSTEM_DEFAULTS = {
    "language": "auto",
}


async def default_phone_options(db: AsyncSession, server) -> dict:
    """Valeurs Simple IP : defauts systeme + valeurs par defaut du serveur (son template global « par defaut »). Remplissent
    un nouveau modele de provisionnement et s'appliquent aux postes sans modele."""
    options = dict(PHONE_OPTION_SYSTEM_DEFAULTS)
    if server:
        gt = (await db.execute(select(GlobalTemplate).where(GlobalTemplate.server_id == server.id, GlobalTemplate.is_default == True,
                                                           GlobalTemplate.is_active == True))).scalar_one_or_none()
        if gt:
            options.update(gt.options or {})
    return options





@router.get("/{phone_id}/config", response_class=PlainTextResponse)
async def get_phone_config(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db), record: bool = True):
    """Returns rendered provisioning config for the phone. No auth — phones fetch this directly."""
    result = await db.execute(
        select(ProvisionedPhone)
        .options(selectinload(ProvisionedPhone.buttons))
        .where(ProvisionedPhone.id == phone_id)
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

    btn_template = None
    if phone.button_template_id:
        bt = await db.execute(select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items))
                              .where(PhoneButtonTemplate.id == phone.button_template_id))
        btn_template = bt.scalar_one_or_none()

    ext = None
    tenant = None
    server = None
    if phone.extension_id:
        e = await db.execute(
            select(SIPExtension)
            .options(selectinload(SIPExtension.tenant).selectinload(Tenant.server))
            .where(SIPExtension.id == phone.extension_id)
        )
        ext = e.scalar_one_or_none()
        if ext:
            tenant = ext.tenant
            server = tenant.server if tenant else None

    # Options du telephone (TASK-051, 2026-10-14, Philippe : « c'est toutes des templates par modele ») : valeurs Simple IP
    # (systeme + valeurs par defaut du serveur) -> modele de provisionnement choisi pour le poste -> ajustements du poste.
    # Plus de niveaux compagnie / bibliotheques de templates (l'ancienne chaine a 5 niveaux de TASK-S044).
    options = await default_phone_options(db, server)
    if btn_template and btn_template.options:
        options.update(btn_template.options)
    if phone.extra_config:
        options.update(phone.extra_config)
    pcodes = {**to_pcodes(await default_phone_options(db, server)),
              **to_pcodes(btn_template.options if btn_template else None), **to_pcodes(phone.extra_config)}
    named = {"P" + x for x in re.findall(r"<P(\d+)>", template_text)}
    extra_pcodes = [(k[1:], v) for k, v in sorted(pcodes.items(), key=lambda kv: int(kv[0][1:]))
                    if k not in named and k not in MANAGED]

    context: dict[str, Any] = {
        "phone": phone,
        "extension": ext,
        # Mot de passe SIP dechiffre a part -- ext.password est stocke chiffre
        # (Fernet, meme convention que xml_curl.py) et ne doit jamais transiter
        # tel quel dans un template.
        "ext_password": _decrypt(ext.password) if ext else "",
        "tenant": tenant,
        "server": server,
        "mac": phone.mac_address.replace(":", "").lower(),
        "options": options,
        # Options en P-codes (TASK-051, 2026-10-14) : lues par le gabarit avec repli Simple IP, et ajoutees a la fin
        "pcodes": pcodes,
        "extra_pcodes": extra_pcodes,
        "buttons": sorted(phone.buttons, key=lambda b: (b.page, b.position)),
        # Touches a leurs vrais codes Grandstream, par modele (0072) : celles du modele de provisionnement du poste, puis
        # les ajustements du poste (meme place = remplace). Boutons sous l'ecran : seulement avec un modele (0073).
        "vpk_keys": vpk_keys(merge_keys(btn_template.items if btn_template else [], phone.buttons), model.model if model else None),
        # Boutons sous l'ecran : ceux du modele, puis les etats personnalises du poste (0075)
        "softkey_items": softkey_items({"layouts": {**normalize_layouts((btn_template.softkeys or {}).get("layouts") if btn_template else None),
                                                    **normalize_layouts((phone.softkeys or {}).get("layouts"))}})
                         if btn_template or phone.softkeys else [],
        "config_host": f"{settings.SIPV_HOST}:8020",
        "provision_host": settings.SIPV_HOST,
        # P48 (proxy SIP) : adresse publique (0069), sauf poste coche « Interne » -> adresse interne de son serveur
        # (TASK-027.3). P237 : le telephone demande /cfg<mac> au serveur web (0068).
        "sip_proxy_host": internal_address(server) if ext and ext.internal_network else settings.SIPV_PUBLIC_IP,
    }

    try:
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(template_text)
        rendered = tmpl.render(**context)
    except TemplateError as e:
        raise HTTPException(status_code=500, detail=f"Erreur template: {e}")

    # Date de la config prise : seulement quand c'est un telephone qui la demande (un test depuis le serveur ne compte pas)
    if record:
        phone.last_provisioned = datetime.now(timezone.utc)
        await db.commit()

    return rendered


@router.get("/gs/cfg{mac_hex}", response_class=PlainTextResponse)
async def grandstream_config(mac_hex: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Adresse standard Grandstream (TASK-051 cote ERPCRM, 2026-10-10) : un telephone dont le serveur de configuration
    est seulement l adresse du serveur demande « /cfg<mac> » a la racine (le serveur web y renvoie ici). Repond la
    configuration du telephone directement (sans redirection)."""
    hexa = mac_hex.lower().removesuffix(".xml")
    if len(hexa) != 12 or any(c not in "0123456789abcdef" for c in hexa):
        raise HTTPException(status_code=404, detail="MAC invalide")
    mac = ":".join(hexa[i:i + 2] for i in range(0, 12, 2)).upper()
    phone = (await db.execute(select(ProvisionedPhone).where(ProvisionedPhone.mac_address == mac))).scalar_one_or_none()
    if not phone:
        raise HTTPException(status_code=404, detail="MAC non enregistrée")
    return await get_phone_config(phone.id, db, record="Grandstream" in request.headers.get("user-agent", ""))


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


# ── Modeles de provisionnement (TASK-023.25 ; refaits TASK-051, 2026-10-14) ──────────
# Philippe : « c'est LA place » -- crees et modifies dans Telephonie -> Provisionnement de la compagnie, par modele de
# telephone (touches par page + boutons sous l'ecran) ; « Sauvegarder comme modele » depuis un poste ajoute au meme
# endroit ; un poste choisit un modele de son modele de telephone (lien, pas copie).

class ButtonTemplateItemIn(BaseModel):
    position: int
    page: int = 0
    button_type: str
    label: str | None = None
    value: str | None = None
    sip_account_index: int = 1

class ButtonTemplateItemOut(ButtonTemplateItemIn):
    id: uuid.UUID

class ButtonTemplateOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    phone_model_id: uuid.UUID | None
    phone_model: str | None
    pages: int
    options: dict | None
    softkeys: dict | None
    phones: int                     # postes qui l'utilisent
    created_at: datetime
    items: list[ButtonTemplateItemOut] = []

class ButtonTemplateIn(BaseModel):
    name: str
    phone_model_id: uuid.UUID
    pages: int = 1
    options: dict | None = None
    softkeys: dict | None = None
    items: list[ButtonTemplateItemIn] = []

class SaveAsTemplatePayload(BaseModel):
    name: str

class PhoneTemplateLink(BaseModel):
    button_template_id: uuid.UUID | None


async def _template_out(db: AsyncSession, t: PhoneButtonTemplate) -> ButtonTemplateOut:
    model = await db.get(PhoneModel, t.phone_model_id) if t.phone_model_id else None
    used = (await db.execute(select(ProvisionedPhone.id).where(ProvisionedPhone.button_template_id == t.id))).all()
    return ButtonTemplateOut(
        id=t.id, tenant_id=t.tenant_id, name=t.name, phone_model_id=t.phone_model_id,
        phone_model=model.model if model else None, pages=t.pages, options=t.options,
        softkeys={"layouts": normalize_layouts((t.softkeys or {}).get("layouts"))} if t.softkeys else None, phones=len(used),
        created_at=t.created_at,
        items=[ButtonTemplateItemOut(id=i.id, position=i.position, page=i.page, button_type=i.button_type,
                                     label=i.label, value=i.value, sip_account_index=i.sip_account_index)
               for i in sorted(t.items or [], key=lambda i: (i.page, i.position))],
    )


async def _load_template(db: AsyncSession, template_id: uuid.UUID) -> PhoneButtonTemplate:
    t = (await db.execute(select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items))
                          .where(PhoneButtonTemplate.id == template_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Modèle introuvable")
    return t


async def _check_template(db: AsyncSession, payload: ButtonTemplateIn) -> None:
    """Refuse ce que le telephone ne peut pas recevoir : modele sans disposition connue, touche hors du telephone,
    mode inconnu, Ligne sur une touche des pages suivantes."""
    model = await db.get(PhoneModel, payload.phone_model_id)
    cat = key_catalog(model.model if model else None)
    if not cat:
        raise HTTPException(status_code=422, detail="Ce modèle de téléphone n'a pas encore de disposition de touches")
    bad = managed_in(payload.options)
    if bad:
        raise HTTPException(status_code=422, detail=f"Réglé par SIPV, pas dans un modèle : {', '.join(bad)}")
    if not 1 <= payload.pages <= cat["pages"]:
        raise HTTPException(status_code=422, detail=f"Ce téléphone a au plus {cat['pages']} pages")
    seen = set()
    for i in payload.items:
        n = i.page * cat["per_page"] + i.position
        if not (0 <= i.page < payload.pages and 1 <= i.position <= cat["per_page"] and n <= cat["total"]):
            raise HTTPException(status_code=422, detail=f"Touche {i.position} de la page {i.page + 1} : hors du téléphone")
        if n in seen:
            raise HTTPException(status_code=422, detail=f"Touche {i.position} de la page {i.page + 1} en double")
        seen.add(n)
        if not 1 <= i.sip_account_index <= cat["accounts"]:
            raise HTTPException(status_code=422, detail=f"Touche {i.position} de la page {i.page + 1} : ce téléphone a {cat['accounts']} comptes")
        if i.button_type not in GS_KEY_MODES:
            raise HTTPException(status_code=422, detail=f"Mode inconnu : {i.button_type}")
        if n > cat["fixed"] and i.button_type in ("line", "shared_line"):
            raise HTTPException(status_code=422, detail=f"Page {i.page + 1}, touche {i.position} : une ligne n'est possible que sur une touche physique")


def _set_items(t: PhoneButtonTemplate, items: list[ButtonTemplateItemIn]) -> None:
    t.items = [PhoneButtonTemplateItem(position=i.position, page=i.page, button_type=i.button_type,
                                       label=(i.label or None), value=(i.value or None), sip_account_index=i.sip_account_index)
               for i in items if i.button_type != "none"]


@router.get("/key-catalog/{model_id}")
async def get_key_catalog(model_id: uuid.UUID, tenant_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Touches, modes et boutons sous l'ecran offerts pour un modele de telephone (gabarit officiel)."""
    model = await db.get(PhoneModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Modèle de téléphone introuvable")
    server = None
    if tenant_id:
        tenant = await db.get(Tenant, tenant_id)
        server = await db.get(SipvServer, tenant.server_id) if tenant and tenant.server_id else None
    return {"model": model.model, "brand": model.brand, "catalog": key_catalog(model.model),
            "default_options": await default_phone_options(db, server)}


@router.get("/option-catalog/{model_id}")
async def get_option_catalog(model_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Arbre des options du telephone (sections -> options), tire du gabarit officiel ; null si le modele n'en a pas."""
    model = await db.get(PhoneModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Modèle de téléphone introuvable")
    return {"model": model.model, "brand": model.brand, "catalog": option_catalog(model.model)}


@router.get("/button-templates/tenant/{tenant_id}", response_model=list[ButtonTemplateOut])
async def list_button_templates(tenant_id: uuid.UUID, phone_model_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    q = select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items)).where(PhoneButtonTemplate.tenant_id == tenant_id)
    if phone_model_id:
        q = q.where(PhoneButtonTemplate.phone_model_id == phone_model_id)
    return [await _template_out(db, t) for t in (await db.execute(q.order_by(PhoneButtonTemplate.name))).scalars().all()]


@router.post("/button-templates/tenant/{tenant_id}", response_model=ButtonTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_button_template(tenant_id: uuid.UUID, payload: ButtonTemplateIn, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    if not await db.get(Tenant, tenant_id):
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    await _check_template(db, payload)
    t = PhoneButtonTemplate(tenant_id=tenant_id, name=payload.name.strip(), phone_model_id=payload.phone_model_id,
                            pages=payload.pages, options=payload.options, softkeys=payload.softkeys, items=[])
    _set_items(t, payload.items)
    db.add(t)
    await db.commit()
    return await _template_out(db, await _load_template(db, t.id))


@router.put("/button-templates/{template_id}", response_model=ButtonTemplateOut)
async def update_button_template(template_id: uuid.UUID, payload: ButtonTemplateIn, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await _load_template(db, template_id)
    await _check_template(db, payload)
    if payload.phone_model_id != t.phone_model_id:
        used = (await db.execute(select(ProvisionedPhone.id).where(ProvisionedPhone.button_template_id == t.id))).first()
        if used:
            raise HTTPException(status_code=422, detail="Des postes utilisent ce modèle : on ne peut pas changer son modèle de téléphone")
    t.name, t.phone_model_id, t.pages, t.options, t.softkeys = (payload.name.strip(), payload.phone_model_id, payload.pages,
                                                                 payload.options, payload.softkeys)
    _set_items(t, payload.items)
    await db.commit()
    return await _template_out(db, await _load_template(db, template_id))


@router.delete("/button-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_button_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await _load_template(db, template_id)
    if (await db.execute(select(ProvisionedPhone.id).where(ProvisionedPhone.button_template_id == t.id))).first():
        raise HTTPException(status_code=422, detail="Des postes utilisent ce modèle : choisissez-leur un autre modèle d'abord")
    await db.delete(t)
    await db.commit()


@router.post("/{phone_id}/save-as-template", response_model=ButtonTemplateOut, status_code=status.HTTP_201_CREATED)
async def save_phone_as_template(phone_id: uuid.UUID, payload: SaveAsTemplatePayload, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Les touches du poste deviennent un modele de la compagnie (meme liste que Telephonie -> Provisionnement) et le
    poste l'utilise."""
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    model = await db.get(PhoneModel, phone.phone_model_id) if phone.phone_model_id else None
    cat = key_catalog(model.model if model else None)
    if not cat:
        raise HTTPException(status_code=422, detail="Ce modèle de téléphone n'a pas encore de disposition de touches")
    buttons = (await db.execute(select(PhoneButton).where(PhoneButton.provisioned_phone_id == phone_id))).scalars().all()
    payload_in = ButtonTemplateIn(name=payload.name, phone_model_id=model.id,
                                  pages=max([b.page + 1 for b in buttons] + [1]),
                                  items=[ButtonTemplateItemIn(position=b.position, page=b.page, button_type=b.button_type,
                                                              label=b.label, value=b.value or b.destination,
                                                              sip_account_index=b.sip_account_index) for b in buttons])
    await _check_template(db, payload_in)
    tenant = await db.get(Tenant, phone.tenant_id)
    server = await db.get(SipvServer, tenant.server_id) if tenant and tenant.server_id else None
    options = {**await default_phone_options(db, server), **(phone.extra_config or {})}
    t = PhoneButtonTemplate(tenant_id=phone.tenant_id, name=payload.name.strip(), phone_model_id=model.id,
                            pages=payload_in.pages, options=options, items=[])
    _set_items(t, payload_in.items)
    db.add(t)
    await db.flush()
    # Le poste utilise son nouveau modele ; ses touches et options y sont passees (plus d'ajustement en double)
    phone.button_template_id = t.id
    phone.extra_config = None
    for b in buttons:
        await db.delete(b)
    await db.commit()
    return await _template_out(db, await _load_template(db, t.id))


@router.get("/{phone_id}/button-templates", response_model=list[ButtonTemplateOut])
async def list_phone_button_templates(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Modeles qu'un poste peut choisir : ceux de sa compagnie pour son modele de telephone."""
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    q = (select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items))
         .where(PhoneButtonTemplate.tenant_id == phone.tenant_id, PhoneButtonTemplate.phone_model_id == phone.phone_model_id)
         .order_by(PhoneButtonTemplate.name))
    return [await _template_out(db, t) for t in (await db.execute(q)).scalars().all()]


class PhoneProvisioningIn(BaseModel):
    extra_config: dict | None = None
    softkeys: dict | None = None
    buttons: list[ButtonTemplateItemIn] = []


@router.put("/{phone_id}/provisioning", response_model=PhoneOut)
async def save_phone_provisioning(phone_id: uuid.UUID, payload: PhoneProvisioningIn, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Onglet « Provisionnement » du poste (2026-10-14) : ce que le poste personnalise par-dessus son modele -- options,
    touches (une touche du poste remplace celle du modele a la meme place) et boutons sous l'ecran -- enregistre d'un coup."""
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    model = await db.get(PhoneModel, phone.phone_model_id) if phone.phone_model_id else None
    cat = key_catalog(model.model if model else None)
    if payload.buttons:
        if not cat:
            raise HTTPException(status_code=422, detail="Ce modèle de téléphone n'a pas encore de disposition de touches")
        await _check_template(db, ButtonTemplateIn(name="poste", phone_model_id=model.id, pages=cat["pages"], items=payload.buttons))
    for b in (await db.execute(select(PhoneButton).where(PhoneButton.provisioned_phone_id == phone_id))).scalars().all():
        await db.delete(b)
    await db.flush()
    for i in payload.buttons:
        db.add(PhoneButton(provisioned_phone_id=phone_id, position=i.position, page=i.page, button_type=i.button_type,
                           label=i.label or None, value=i.value or None, sip_account_index=i.sip_account_index))
    bad = managed_in(payload.extra_config)
    if bad:
        raise HTTPException(status_code=422, detail=f"Réglé par SIPV, pas dans un poste : {', '.join(bad)}")
    phone.extra_config = payload.extra_config or None
    phone.softkeys = payload.softkeys if (payload.softkeys or {}).get("layouts") else None
    await db.commit()
    await db.refresh(phone)
    return _phone_out(phone)


@router.put("/{phone_id}/button-template", response_model=PhoneOut)
async def set_phone_button_template(phone_id: uuid.UUID, payload: PhoneTemplateLink, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Choisit le modele de provisionnement du poste (ceux de sa compagnie, pour son modele de telephone) ; aucun = ses
    propres touches. S'applique au prochain chargement de configuration du telephone."""
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    if payload.button_template_id:
        t = await db.get(PhoneButtonTemplate, payload.button_template_id)
        if not t or t.tenant_id != phone.tenant_id:
            raise HTTPException(status_code=404, detail="Modèle introuvable pour cette compagnie")
        if t.phone_model_id != phone.phone_model_id:
            raise HTTPException(status_code=422, detail="Ce modèle est pour un autre modèle de téléphone")
    phone.button_template_id = payload.button_template_id
    await db.commit()
    await db.refresh(phone)
    return _phone_out(phone)


# ── Tenant-Model Templates -- chaine d'heritage a 5 niveaux (TASK-S044) ──
# TenantTemplate a demenage dans servers.py (bibliotheque par serveur,
# TASK-S044.1) -- reste ici seulement ce qui est cree/scope par compagnie.
class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    options: dict
    is_default: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class TenantModelTemplateOut(TemplateOut):
    tenant_id: uuid.UUID
    phone_model_id: uuid.UUID

class TenantModelTemplateCreate(BaseModel):
    tenant_id: uuid.UUID
    phone_model_id: uuid.UUID
    name: str
    description: str | None = None
    options: dict = {}
    is_default: bool = False
    is_active: bool = True

class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    options: dict | None = None
    is_default: bool | None = None
    is_active: bool | None = None



@router.get("/tenant-model-templates/tenant/{tenant_id}", response_model=list[TenantModelTemplateOut])
async def list_tenant_model_templates(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(TenantModelTemplate).where(TenantModelTemplate.tenant_id == tenant_id).order_by(TenantModelTemplate.name))
    return result.scalars().all()


@router.post("/tenant-model-templates", response_model=TenantModelTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_tenant_model_template(payload: TenantModelTemplateCreate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    if payload.is_default:
        await db.execute(update(TenantModelTemplate).where(
            TenantModelTemplate.tenant_id == payload.tenant_id, TenantModelTemplate.phone_model_id == payload.phone_model_id,
        ).values(is_default=False))
    t = TenantModelTemplate(**payload.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@router.put("/tenant-model-templates/{template_id}", response_model=TenantModelTemplateOut)
async def update_tenant_model_template(template_id: uuid.UUID, payload: TemplateUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await db.get(TenantModelTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    if payload.is_default:
        await db.execute(update(TenantModelTemplate).where(
            TenantModelTemplate.tenant_id == t.tenant_id, TenantModelTemplate.phone_model_id == t.phone_model_id, TenantModelTemplate.id != t.id,
        ).values(is_default=False))
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return t


@router.delete("/tenant-model-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_model_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    t = await db.get(TenantModelTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    await db.delete(t)
    await db.commit()
