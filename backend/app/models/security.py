import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import enum


class SecurityEvent(Base):
    """Audit log for security-relevant events (auth failures, ACL blocks, fraud alerts)."""
    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)   # auth_fail, acl_block, fraud_alert, brute_force
    severity: Mapped[str] = mapped_column(String(10), default="info")     # info, warning, critical
    source_ip: Mapped[str | None] = mapped_column(String(45))
    username: Mapped[str | None] = mapped_column(String(100))             # SIP username or similar
    description: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ACLRule(Base):
    """IP-based ACL rules — allow or deny CIDR blocks per tenant or globally."""
    __tablename__ = "acl_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"))
    cidr: Mapped[str] = mapped_column(String(50), nullable=False)         # e.g. 192.168.1.0/24
    action: Mapped[str] = mapped_column(String(5), nullable=False)        # allow / deny
    description: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[int] = mapped_column(Integer, default=100)           # lower = evaluated first
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FraudRule(Base):
    """Fraud detection thresholds per tenant."""
    __tablename__ = "fraud_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    max_calls_per_hour: Mapped[int | None] = mapped_column(Integer)      # concurrent or total
    max_concurrent_calls: Mapped[int | None] = mapped_column(Integer)
    max_international_calls_per_day: Mapped[int | None] = mapped_column(Integer)
    block_international: Mapped[bool] = mapped_column(Boolean, default=False)
    block_premium: Mapped[bool] = mapped_column(Boolean, default=True)   # 1-900 / 976 / etc.
    alert_email: Mapped[str | None] = mapped_column(String(255))
    auto_block_on_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BlockedIP(Base):
    """IPs/usernames blocked by fail2ban equivalent logic."""
    __tablename__ = "blocked_ips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(String(200))
    block_count: Mapped[int] = mapped_column(Integer, default=1)          # how many times blocked
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))   # None = permanent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
