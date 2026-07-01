import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Tenant(Base):
    """Maps to an ERPCRM company (account_number = tenant_id in Asterisk)."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # account_number from ERPCRM company
    account_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ERPCRM company UUID for sync
    erpcrm_company_id: Mapped[str | None] = mapped_column(String(36))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Context prefix in Asterisk: from-{account_number}-internal, from-{account_number}-external
    context_prefix: Mapped[str] = mapped_column(String(50), nullable=False)
    max_extensions: Mapped[int] = mapped_column(Integer, default=10)
    max_trunks: Mapped[int] = mapped_column(Integer, default=2)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    extensions: Mapped[list["SIPExtension"]] = relationship("SIPExtension", back_populates="tenant", cascade="all, delete-orphan")
    trunks: Mapped[list["SIPTrunk"]] = relationship("SIPTrunk", back_populates="tenant", cascade="all, delete-orphan")
    dids: Mapped[list["TenantDID"]] = relationship("TenantDID", back_populates="tenant", cascade="all, delete-orphan")
