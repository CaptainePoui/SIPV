import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class PhoneModel(Base):
    """Phone hardware model template (Grandstream GXP2160, Yealink T46U, etc.)"""
    __tablename__ = "phone_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand: Mapped[str] = mapped_column(String(40), nullable=False)   # Grandstream, Yealink, Polycom
    model: Mapped[str] = mapped_column(String(60), nullable=False)   # GXP2160, T46U
    firmware_version: Mapped[str | None] = mapped_column(String(30))
    # TASK-023.13 -- telephone/ATA/softphone/intercom
    device_type: Mapped[str] = mapped_column(String(20), default="telephone", server_default="telephone")
    max_accounts: Mapped[int] = mapped_column(default=1)
    provisioning_protocol: Mapped[str] = mapped_column(String(20), default="http")  # http, https, tftp
    config_template: Mapped[str | None] = mapped_column(Text)        # Jinja2 template text
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProvisionedPhone(Base):
    """A physical phone assigned to a tenant extension."""
    __tablename__ = "provisioned_phones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    extension_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_extensions.id", ondelete="SET NULL"))
    phone_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("phone_models.id", ondelete="SET NULL"))
    mac_address: Mapped[str] = mapped_column(String(17), nullable=False, unique=True)  # AA:BB:CC:DD:EE:FF
    display_name: Mapped[str | None] = mapped_column(String(60))
    location: Mapped[str | None] = mapped_column(String(100))        # e.g. "Réception bureau 3"
    ip_address: Mapped[str | None] = mapped_column(String(45))       # last known IP
    firmware_version: Mapped[str | None] = mapped_column(String(30))
    last_provisioned: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_config: Mapped[dict | None] = mapped_column(JSON)          # override key-value pairs
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # TASK-S044.2 -- PLUSIEURS templates par modele choisis explicitement pour
    # ce poste (ex: "defaut" + "oreillette" + "boutons de park"), fusionnes
    # dans l'ordre du tableau. Tableau vide = aucun, la chaine d'heritage saute
    # ce niveau.
    selected_tenant_model_template_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")

    # --- TASK-S011.2 : fiche physique du poste ---
    serial_number: Mapped[str | None] = mapped_column(String(60))
    hardware_version: Mapped[str | None] = mapped_column(String(30))
    # Mot de passe admin du telephone, chiffre (Fernet, meme pattern que ClientAccess
    # cote ERPCRM) -- jamais stocke en clair.
    encrypted_admin_password: Mapped[str | None] = mapped_column(Text)
    wifi_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    bluetooth_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    headset_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expansion_module: Mapped[str | None] = mapped_column(String(60))  # modele du module, null = aucun
    # --- TASK-023.31 : reglages reseau/provisioning du poste ---
    # Protocole de recuperation du fichier de config par le telephone lui-meme
    # (equivalent du "Config Server Path" Grandstream). https = defaut (le plus
    # securise) -- le pont automatique cfg<MAC>.xml n'est pas encore cable
    # (TASK-S011.4), ce champ prepare seulement le reglage cote fiche.
    provisioning_protocol: Mapped[str] = mapped_column(String(10), default="https", server_default="https")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    buttons: Mapped[list["PhoneButton"]] = relationship("PhoneButton", back_populates="phone", cascade="all, delete-orphan")


class PhoneButton(Base):
    """
    Bouton/touche programmable d'un telephone physique (TASK-023.17). Editeur en
    LISTE -- decouple de TASK-S011.3 (mapping visuel sur photo, toujours bloque
    faute de photo) : ce sont les MEMES donnees (position/type/destination), mais
    accessibles/editables sans attendre une image cliquable.
    """
    __tablename__ = "phone_buttons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provisioned_phone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("provisioned_phones.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # ligne, blf, speed_dial, park, park_retrieve, voicemail, transfer, intercom,
    # paging, dnd, forward, queue, agent_login, agent_logout, agent_pause,
    # pickup_group, feature_code, door, directory
    button_type: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str | None] = mapped_column(String(60))
    value: Mapped[str | None] = mapped_column(String(100))  # code de fonction, chiffres de composition rapide, etc.
    destination: Mapped[str | None] = mapped_column(String(100))  # poste/groupe/file cible selon button_type
    sip_account_index: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # quel compte SIP du telephone
    client_editable: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by_simpleip: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    phone: Mapped["ProvisionedPhone"] = relationship("ProvisionedPhone", back_populates="buttons")


class PhoneButtonTemplate(Base):
    """Modele de configuration de boutons reutilisable (TASK-023.25) -- cree a
    partir d'un ProvisionedPhone existant, applicable a d'autres appareils."""
    __tablename__ = "phone_button_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    items: Mapped[list["PhoneButtonTemplateItem"]] = relationship("PhoneButtonTemplateItem", back_populates="template", cascade="all, delete-orphan")


class PhoneButtonTemplateItem(Base):
    """Un bouton dans un template (TASK-023.25) -- memes champs que PhoneButton,
    sans provisioned_phone_id (pas encore attache a un appareil precis)."""
    __tablename__ = "phone_button_template_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("phone_button_templates.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    button_type: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str | None] = mapped_column(String(60))
    value: Mapped[str | None] = mapped_column(String(100))
    destination: Mapped[str | None] = mapped_column(String(100))
    sip_account_index: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    client_editable: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by_simpleip: Mapped[bool] = mapped_column(Boolean, default=True)

    template: Mapped["PhoneButtonTemplate"] = relationship("PhoneButtonTemplate", back_populates="items")


# --- TASK-S044/TASK-S044.1 : chaine d'heritage a 5 niveaux du catalogue
# d'options (item 1 de TASK-S043/TASK-027) -- modele calque sur le doc source
# UCM Grandstream (schema_champs_ucm.md, onglet Zero Config) : Global Policy =
# singleton (deja Tenant.phone_option_defaults, TASK-S011.5). GlobalTemplate =
# bibliotheque par serveur, is_default = applique automatiquement a tous les
# tenants du serveur (pas de choix explicite -- comportement "policy").
# TenantTemplate = bibliotheque par serveur aussi, mais JAMAIS automatique --
# chaque compagnie doit choisir explicitement lequel elle utilise
# (Tenant.selected_tenant_template_id, revise TASK-S044.1 suite a la demande
# de Philippe : "create template" dans la couche superieure de la hierarchie
# -- Serveur -- le choix dans la couche adequate -- Compagnie). Meme principe
# pour TenantModelTemplate (cree dans Compagnie, choisi dans Contact via
# ProvisionedPhone.selected_tenant_model_template_id). "options" utilise les
# memes cles que PHONE_OPTIONS_CATALOG (ref_data.py cote ERPCRM,
# TASK-S011.6/TASK-023.28) -- une cle absente du dict = "as template" (suit
# la valeur du template choisi), presente = personnalisee.
class GlobalTemplate(Base):
    """Gabarit d'options partage par TOUS les tenants d'un serveur SIPV --
    equivalent serveur de l'onglet "Global Templates" UCM (qui se superpose a
    la Global Policy)."""
    __tablename__ = "global_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sipv_servers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TenantTemplate(Base):
    """Bibliotheque de gabarits d'options partagee par serveur (TASK-S044.1) --
    memes esprit/colonnes que GlobalTemplate, mais NON applique automatiquement :
    chaque compagnie choisit explicitement lequel elle utilise
    (Tenant.selected_tenant_template_id), pour ajuster son
    Tenant.phone_option_defaults ("Global Policy" du tenant)."""
    __tablename__ = "tenant_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sipv_servers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TenantModelTemplate(Base):
    """Gabarit d'options propre a un tenant ET a un modele de telephone
    precis -- equivalent tenant de l'onglet "Model Templates" UCM (memes
    colonnes Model/Is Default), vient se superposer au TenantTemplate."""
    __tablename__ = "tenant_model_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    phone_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("phone_models.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
