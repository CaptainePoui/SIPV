import uuid
from datetime import datetime, timezone, date, time
from sqlalchemy import String, Boolean, DateTime, Date, Time, Integer, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Schedule(Base):
    """Business hours schedule for IVR routing decisions."""
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="America/Montreal")
    # Fallback destination when outside hours
    closed_destination_type: Mapped[str | None] = mapped_column(String(20))  # voicemail, ivr, hangup
    closed_destination: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ScheduleRule(Base):
    """Weekly recurrence rules for a schedule (Mon-Fri 9am-5pm, etc.)."""
    __tablename__ = "schedule_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    # days_of_week: comma-sep 0=Mon … 6=Sun
    days_of_week: Mapped[str] = mapped_column(String(20), nullable=False, default="0,1,2,3,4")
    open_time: Mapped[time] = mapped_column(Time, nullable=False)       # e.g. 09:00
    close_time: Mapped[time] = mapped_column(Time, nullable=False)      # e.g. 17:00
    label: Mapped[str | None] = mapped_column(String(60))


class Holiday(Base):
    """Specific dates when the tenant is closed (override schedule)."""
    __tablename__ = "holidays"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Optional: override destination on this day instead of closed_destination
    override_destination_type: Mapped[str | None] = mapped_column(String(20))
    override_destination: Mapped[str | None] = mapped_column(String(100))
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)     # same date every year
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
