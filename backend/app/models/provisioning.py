import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
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
