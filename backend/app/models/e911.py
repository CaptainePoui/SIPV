import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class E911Address(Base):
    """Validated 911 civic address for a tenant location."""
    __tablename__ = "e911_addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "Bureau principal"
    # Civic address fields (NENA NG911 format)
    civic_number: Mapped[str] = mapped_column(String(20), nullable=False)
    street_name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(60), nullable=False)
    province: Mapped[str] = mapped_column(String(2), nullable=False)   # QC, ON, etc.
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="CA")
    # Carrier submission status
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)   # confirmed by carrier
    carrier_reference: Mapped[str | None] = mapped_column(String(100))   # ref from carrier
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DID911Assignment(Base):
    """Links a DID to an E911 address and tracks 911 capability."""
    __tablename__ = "did_911_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    did_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_dids.id", ondelete="CASCADE"), nullable=False, unique=True)
    e911_address_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("e911_addresses.id", ondelete="CASCADE"), nullable=False)
    # 911 outbound routing override (which trunk to use for 911 calls)
    emergency_trunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_trunks.id", ondelete="SET NULL"))
    # Alerts
    alert_email: Mapped[str | None] = mapped_column(String(255))    # notify on 911 call
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
