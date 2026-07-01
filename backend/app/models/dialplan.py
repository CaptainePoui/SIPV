import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class OutboundRoute(Base):
    """Outbound dial pattern route — matches dialed number and sends to a trunk."""
    __tablename__ = "outbound_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Dial patterns — comma-separated, e.g. "NXXNXXXXXX,1NXXNXXXXXX,011."
    dial_patterns: Mapped[str] = mapped_column(Text, nullable=False)
    trunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_trunks.id", ondelete="CASCADE"), nullable=False)
    # Strip leading digits from dialed number before sending to trunk
    strip_digits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Prefix to add to dialed number before sending
    prepend_digits: Mapped[str | None] = mapped_column(String(20))
    # Caller ID override for outbound
    caller_id_override: Mapped[str | None] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    asterisk_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class InboundRoute(Base):
    """Maps an inbound DID to a destination."""
    __tablename__ = "inbound_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    did_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_dids.id", ondelete="SET NULL"))
    # DID number (denormalized for Asterisk context)
    did_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(20), nullable=False, default="extension")
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    # Business hours schedule ID (optional, for SIPV-T-024)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    asterisk_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
