import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Numeric, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CDR(Base):
    """Call Detail Record — every call logged here."""
    __tablename__ = "cdr"
    __table_args__ = (
        Index("ix_cdr_tenant_id", "tenant_id"),
        Index("ix_cdr_start_time", "start_time"),
        Index("ix_cdr_src", "src"),
        Index("ix_cdr_dst", "dst"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    # Asterisk CDR fields
    accountcode: Mapped[str | None] = mapped_column(String(20))  # = account_number
    src: Mapped[str | None] = mapped_column(String(80))          # calling party
    dst: Mapped[str | None] = mapped_column(String(80))          # called party
    dcontext: Mapped[str | None] = mapped_column(String(80))     # destination context
    clid: Mapped[str | None] = mapped_column(String(80))         # caller ID string
    channel: Mapped[str | None] = mapped_column(String(80))
    dstchannel: Mapped[str | None] = mapped_column(String(80))
    lastapp: Mapped[str | None] = mapped_column(String(80))      # last Asterisk app
    lastdata: Mapped[str | None] = mapped_column(String(80))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration: Mapped[int | None] = mapped_column(Integer)        # seconds total
    billsec: Mapped[int | None] = mapped_column(Integer)         # seconds billed
    disposition: Mapped[str | None] = mapped_column(String(45))  # ANSWERED, NO ANSWER, BUSY, FAILED
    amaflags: Mapped[int | None] = mapped_column(Integer)        # 1=OMIT 2=BILLING 3=DOCUMENTATION
    userfield: Mapped[str | None] = mapped_column(String(255))
    uniqueid: Mapped[str | None] = mapped_column(String(150))    # Asterisk unique call ID
    linkedid: Mapped[str | None] = mapped_column(String(150))
    sequence: Mapped[int | None] = mapped_column(Integer)
    # Cost calculation (filled post-call)
    direction: Mapped[str | None] = mapped_column(String(10))    # inbound / outbound
    prefix_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rate_prefixes.id", ondelete="SET NULL"))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    rate_per_minute: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RatePrefix(Base):
    """Tarif d'appel par prefixe NANP/international."""
    __tablename__ = "rate_prefixes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(60))
    region: Mapped[str | None] = mapped_column(String(60))
    rate_per_minute: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    min_duration: Mapped[int] = mapped_column(Integer, default=6)   # minimum billable seconds
    increment: Mapped[int] = mapped_column(Integer, default=6)       # billing increment seconds
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
