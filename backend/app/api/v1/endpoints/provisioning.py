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
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.provisioning import PhoneModel, ProvisionedPhone, PhoneButton, PhoneButtonTemplate, PhoneButtonTemplateItem, GlobalTemplate, TenantTemplate, TenantModelTemplate
from app.models.sip import SIPExtension
from app.models.tenant import Tenant
from app.models.user import User

from app.api.v1.endpoints.internal_devices import internal_address

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

# Touches programmables Grandstream GXP21xx (VPK), lues du gabarit officiel du firmware 1.0.11.106
# (~/GrandStream/Template_Config_Pcode/config-template/gxp2130_40_60_70_35_config_1.0.11.106.txt, 2026-10-14) :
# - touche n <= 6 : mode P1363+2(n-1), compte P1364+2(n-1), description P1465+2(n-1), valeur P1466+2(n-1) ;
# - touche n >= 7 : P23800+4(n-7) (+0 mode, +1 compte, +2 description, +3 valeur).
# Regle verifiee touche par touche pour les 5 modeles du gabarit. (fixes, total) par modele : les touches fixes sont les
# touches physiques (page 1) ; les dynamiques forment les pages suivantes.
GS_VPK_LAYOUT = {"GXP2130": (3, 12), "GXP2140": (4, 16), "GXP2160": (6, 24), "GXP2135": (8, 32), "GXP2170": (12, 48)}

# Modes, legende des touches fixes du gabarit. Une touche dynamique prend le meme code moins 10 (legende « Dynamic VPK »)
# et n'accepte ni Ligne ni Ligne partagee. (L'ancienne table appliquait la legende fixe aux touches dynamiques :
# Parcage 19 = « Information », Parcage surveille 26 = « Verrouillage clavier » -- erreur corrigee le 2026-10-14.)
GS_KEY_MODES = {
    "none": -1, "line": 0, "shared_line": 1, "speed_dial": 10, "blf": 11, "presence_watcher": 12, "eventlist_blf": 13,
    "speed_dial_active": 14, "dial_dtmf": 15, "voicemail": 16, "call_return": 17, "transfer": 18, "park": 19,
    "intercom": 20, "ldap_search": 21, "conference": 22, "paging": 23, "record": 24, "call_log": 25,
    "park_retrieve": 26, "menu": 27, "xml_app": 28, "information": 29, "message": 30, "forward": 31, "dnd": 32,
    "redial": 33, "instant_messages": 34, "multicast_listen": 35, "keypad_lock": 36,
    # Fonctions SIPV sans mode Grandstream propre : BLF sur la file, sinon numerotation rapide du code de fonction
    "queue": 11, "agent_login": 10, "agent_logout": 10, "agent_pause": 10, "pickup_group": 10, "feature_code": 10,
    "door": 10,
}
VPK_KEYS_PER_PAGE = 8


def _vpk_pcodes(n: int) -> tuple[int, int, int, int]:
    if n <= 6:
        return 1363 + 2 * (n - 1), 1364 + 2 * (n - 1), 1465 + 2 * (n - 1), 1466 + 2 * (n - 1)
    base = 23800 + 4 * (n - 7)
    return base, base + 1, base + 2, base + 3


def _vpk_keys(buttons, model_name: str | None) -> list[dict]:
    """Toutes les touches du modele, dans l'ordre (le gabarit : une touche dynamique, meme « aucune », doit etre envoyee
    a sa place). Philippe (2026-10-14) : une page non ajoutee = ses touches a « aucune » -- sinon le telephone garde
    ses anciens reglages."""
    fixed, total = GS_VPK_LAYOUT.get((model_name or "").upper(), (0, 0))
    by_index = {(b.page or 0) * VPK_KEYS_PER_PAGE + b.position: b for b in buttons}
    out = []
    for n in range(1, total + 1):
        b = by_index.get(n)
        mode = GS_KEY_MODES.get(b.button_type, -1) if b else -1
        if n > fixed and mode != -1:
            mode = mode - 10 if mode >= 10 else -1          # Ligne / Ligne partagee impossibles sur une touche dynamique
        pm, pa, pd, pv = _vpk_pcodes(n)
        out.append({"n": n, "p_mode": pm, "p_account": pa, "p_label": pd, "p_value": pv, "mode": mode,
                    "account": (b.sip_account_index - 1) if b else 0,
                    "label": (b.label or "") if b else "",
                    "value": (b.value or b.destination or "") if b else ""})
    return out




@router.get("/{phone_id}/config", response_class=PlainTextResponse)
async def get_phone_config(phone_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
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

    # Fusion du catalogue d'options -- chaine d'heritage a 5 niveaux (TASK-S044/
    # S044.1/S044.2) : systeme -> template(s) global(aux) serveur (celui
    # is_default automatique + ceux choisis explicitement en plus, ex. "defaut"
    # + "oreillette" + "boutons de park") -> Global Policy tenant
    # (phone_option_defaults) -> template(s) du tenant CHOISIS explicitement ->
    # template(s) du modele CHOISIS explicitement -> poste individuel. Le plus
    # specifique gagne ; PLUSIEURS templates possibles au meme niveau, fusionnes
    # dans l'ordre du tableau (le dernier du tableau gagne en cas de cle en
    # commun entre 2 templates du meme niveau). Contrairement au is_default
    # serveur (automatique, "policy"), tenant/modele ne s'appliquent QUE si
    # explicitement choisis -- pas de devinette.
    options = dict(PHONE_OPTION_SYSTEM_DEFAULTS)

    if server:
        gt = await db.execute(
            select(GlobalTemplate).where(
                GlobalTemplate.server_id == server.id,
                GlobalTemplate.is_default == True,
                GlobalTemplate.is_active == True,
            )
        )
        global_template = gt.scalar_one_or_none()
        if global_template:
            options.update(global_template.options or {})

    if tenant and tenant.selected_global_template_ids:
        for tid in tenant.selected_global_template_ids:
            t = await db.get(GlobalTemplate, tid)
            if t and t.is_active:
                options.update(t.options or {})

    if tenant and tenant.phone_option_defaults:
        options.update(tenant.phone_option_defaults)

    if tenant and tenant.selected_tenant_template_ids:
        for tid in tenant.selected_tenant_template_ids:
            t = await db.get(TenantTemplate, tid)
            if t and t.is_active:
                options.update(t.options or {})

    if phone.selected_tenant_model_template_ids:
        for tid in phone.selected_tenant_model_template_ids:
            t = await db.get(TenantModelTemplate, tid)
            if t and t.is_active:
                options.update(t.options or {})

    if phone.extra_config:
        options.update(phone.extra_config)

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
        "buttons": sorted(phone.buttons, key=lambda b: (b.page, b.position)),
        # Touches a leurs vrais codes Grandstream, par modele (0072)
        "vpk_keys": _vpk_keys(phone.buttons, model.model if model else None),
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

    # Update last_provisioned
    phone.last_provisioned = datetime.now(timezone.utc)
    await db.commit()

    return rendered


@router.get("/gs/cfg{mac_hex}", response_class=PlainTextResponse)
async def grandstream_config(mac_hex: str, db: AsyncSession = Depends(get_db)):
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
    return await get_phone_config(phone.id, db)


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


# ── Templates de boutons (TASK-023.25) ──────────────────────────────────────────

class ButtonTemplateItemOut(BaseModel):
    id: uuid.UUID
    position: int
    page: int
    button_type: str
    label: str | None
    value: str | None
    destination: str | None
    sip_account_index: int
    client_editable: bool
    locked_by_simpleip: bool

class ButtonTemplateOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    created_at: datetime
    items: list[ButtonTemplateItemOut] = []

class ButtonTemplateCreate(BaseModel):
    name: str

class SaveAsTemplatePayload(BaseModel):
    name: str


def _template_out(t: PhoneButtonTemplate) -> ButtonTemplateOut:
    return ButtonTemplateOut(
        id=t.id, tenant_id=t.tenant_id, name=t.name, created_at=t.created_at,
        items=[
            ButtonTemplateItemOut(
                id=i.id, position=i.position, page=i.page, button_type=i.button_type,
                label=i.label, value=i.value, destination=i.destination,
                sip_account_index=i.sip_account_index, client_editable=i.client_editable,
                locked_by_simpleip=i.locked_by_simpleip,
            ) for i in (t.items or [])
        ],
    )


@router.get("/button-templates/tenant/{tenant_id}", response_model=list[ButtonTemplateOut])
async def list_button_templates(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(
        select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items))
        .where(PhoneButtonTemplate.tenant_id == tenant_id).order_by(PhoneButtonTemplate.name)
    )
    return [_template_out(t) for t in result.scalars().all()]


@router.delete("/button-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_button_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(PhoneButtonTemplate).where(PhoneButtonTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    await db.delete(t)
    await db.commit()


@router.post("/{phone_id}/save-as-template", response_model=ButtonTemplateOut, status_code=status.HTTP_201_CREATED)
async def save_phone_as_template(phone_id: uuid.UUID, payload: SaveAsTemplatePayload, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Sauvegarde la config de boutons actuelle d'un telephone comme template reutilisable."""
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")
    result = await db.execute(select(PhoneButton).where(PhoneButton.provisioned_phone_id == phone_id))
    buttons = result.scalars().all()
    t = PhoneButtonTemplate(tenant_id=phone.tenant_id, name=payload.name)
    db.add(t)
    await db.flush()
    for b in buttons:
        db.add(PhoneButtonTemplateItem(
            template_id=t.id, position=b.position, page=b.page, button_type=b.button_type,
            label=b.label, value=b.value, destination=b.destination,
            sip_account_index=b.sip_account_index, client_editable=b.client_editable,
            locked_by_simpleip=b.locked_by_simpleip,
        ))
    await db.commit()
    result = await db.execute(select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items)).where(PhoneButtonTemplate.id == t.id))
    return _template_out(result.scalar_one())


@router.post("/button-templates/{template_id}/apply/{phone_id}", response_model=list[PhoneButtonOut])
async def apply_button_template(template_id: uuid.UUID, phone_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """
    Applique un template a un telephone -- REMPLACE les boutons existants de cet
    appareil par ceux du template (semantique "appliquer" simple et predictible,
    pas une fusion).
    """
    result = await db.execute(select(PhoneButtonTemplate).options(selectinload(PhoneButtonTemplate.items)).where(PhoneButtonTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template introuvable")
    phone = await db.get(ProvisionedPhone, phone_id)
    if not phone:
        raise HTTPException(status_code=404, detail="Téléphone introuvable")

    existing = await db.execute(select(PhoneButton).where(PhoneButton.provisioned_phone_id == phone_id))
    for b in existing.scalars().all():
        await db.delete(b)
    await db.flush()

    new_buttons = []
    for item in t.items:
        b = PhoneButton(
            provisioned_phone_id=phone_id, position=item.position, page=item.page,
            button_type=item.button_type, label=item.label, value=item.value,
            destination=item.destination, sip_account_index=item.sip_account_index,
            client_editable=item.client_editable, locked_by_simpleip=item.locked_by_simpleip,
        )
        db.add(b)
        new_buttons.append(b)
    await db.commit()
    for b in new_buttons:
        await db.refresh(b)
    return [_button_out(b) for b in new_buttons]


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
