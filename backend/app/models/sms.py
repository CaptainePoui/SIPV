import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import enum


class SMSProvider(str, enum.Enum):
    twilio = "twilio"
    bandwidth = "bandwidth"
    telnyx = "telnyx"
    sinch = "sinch"
    vonage = "vonage"
    other = "other"


class SMSDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class SMSStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    received = "received"


class SMSConfig(Base):
    """Per-tenant SMS provider configuration."""
    __tablename__ = "sms_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    provider: Mapped[SMSProvider] = mapped_column(Enum(SMSProvider, name="sms_provider_enum"), nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text)          # encrypted
    api_secret: Mapped[str | None] = mapped_column(Text)       # encrypted
    account_sid: Mapped[str | None] = mapped_column(String(100))  # Twilio account SID etc.
    from_number: Mapped[str | None] = mapped_column(String(30))   # default sender number
    webhook_url: Mapped[str | None] = mapped_column(String(255))  # inbound webhook
    monthly_limit: Mapped[int | None] = mapped_column(Integer)    # max outbound per month
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SMSMessage(Base):
    """Individual SMS message (inbound or outbound)."""
    __tablename__ = "sms_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[SMSDirection] = mapped_column(Enum(SMSDirection, name="sms_direction_enum"), nullable=False)
    status: Mapped[SMSStatus] = mapped_column(Enum(SMSStatus, name="sms_status_enum"), default=SMSStatus.queued)
    from_number: Mapped[str] = mapped_column(String(30), nullable=False)
    to_number: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(150))   # provider SID/ID
    provider: Mapped[str | None] = mapped_column(String(20))
    num_segments: Mapped[int | None] = mapped_column(Integer)              # SMS segments
    cost: Mapped[str | None] = mapped_column(String(20))                   # cost string from provider
    error_code: Mapped[str | None] = mapped_column(String(30))
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
