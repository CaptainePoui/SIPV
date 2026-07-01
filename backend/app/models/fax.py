import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, BigInteger, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import enum


class FaxDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class FaxStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    delivered = "delivered"
    failed = "failed"


class FaxLine(Base):
    """A DID configured to receive/send faxes for a tenant."""
    __tablename__ = "fax_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    did_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_dids.id", ondelete="SET NULL"))
    fax_number: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    # Inbound delivery
    delivery_email: Mapped[str | None] = mapped_column(String(255))    # email for received faxes
    # T.38 / SpanDSP settings
    use_t38: Mapped[bool] = mapped_column(Boolean, default=True)
    # ATA device info (if applicable)
    ata_ip: Mapped[str | None] = mapped_column(String(45))
    ata_model: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FaxJob(Base):
    """A sent or received fax document."""
    __tablename__ = "fax_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fax_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("fax_lines.id", ondelete="SET NULL"))
    direction: Mapped[FaxDirection] = mapped_column(Enum(FaxDirection, name="fax_direction_enum"), nullable=False)
    status: Mapped[FaxStatus] = mapped_column(Enum(FaxStatus, name="fax_status_enum"), default=FaxStatus.pending)
    remote_number: Mapped[str | None] = mapped_column(String(30))       # sending/receiving number
    pages: Mapped[int | None] = mapped_column(Integer)
    file_path: Mapped[str | None] = mapped_column(String(500))          # PDF path on disk
    file_size: Mapped[int | None] = mapped_column(BigInteger)           # bytes
    delivery_email: Mapped[str | None] = mapped_column(String(255))     # inbound only
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    asterisk_uniqueid: Mapped[str | None] = mapped_column(String(150))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
