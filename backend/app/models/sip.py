import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SIPExtension(Base):
    """SIP endpoint (extension) for a tenant — mirrors ps_endpoints in Asterisk Realtime."""
    __tablename__ = "sip_extensions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # SIP credentials
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # {tenant_account}-{ext}
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Features
    voicemail_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voicemail_email: Mapped[str | None] = mapped_column(String(255))
    caller_id_name: Mapped[str | None] = mapped_column(String(100))
    caller_id_number: Mapped[str | None] = mapped_column(String(30))
    # Call recording
    record_calls: Mapped[bool] = mapped_column(Boolean, default=False)
    # Max channels
    max_contacts: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Sync state
    freeswitch_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="extensions")

    @property
    def endpoint_name(self) -> str:
        return self.username


class SIPTrunk(Base):
    """SIP trunk connecting to a carrier — mirrors ps_endpoints for trunk in Asterisk."""
    __tablename__ = "sip_trunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(100))
    password: Mapped[str | None] = mapped_column(String(255))
    from_domain: Mapped[str | None] = mapped_column(String(255))
    # Outbound caller ID override
    caller_id: Mapped[str | None] = mapped_column(String(30))
    # Failover trunk
    failover_trunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_trunks.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    freeswitch_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="trunks")


class TenantDID(Base):
    """DID number assigned to a tenant — for inbound routing."""
    __tablename__ = "tenant_dids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(100))
    # Where to route inbound calls
    destination_type: Mapped[str] = mapped_column(String(20), default="extension")  # extension, ivr, queue, voicemail
    destination: Mapped[str | None] = mapped_column(String(100))
    has_911: Mapped[bool] = mapped_column(Boolean, default=False)
    e911_address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="dids")
