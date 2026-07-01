import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PhoneModel(Base):
    """Phone hardware model template (Grandstream GXP2160, Yealink T46U, etc.)"""
    __tablename__ = "phone_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand: Mapped[str] = mapped_column(String(40), nullable=False)   # Grandstream, Yealink, Polycom
    model: Mapped[str] = mapped_column(String(60), nullable=False)   # GXP2160, T46U
    firmware_version: Mapped[str | None] = mapped_column(String(30))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
