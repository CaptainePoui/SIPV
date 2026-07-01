import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, BigInteger, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import enum


class StorageBackend(str, enum.Enum):
    local = "local"
    dropbox = "dropbox"
    onedrive = "onedrive"
    s3 = "s3"


class RecordingPolicy(Base):
    """Per-tenant recording policy and retention rules."""
    __tablename__ = "recording_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    record_inbound: Mapped[bool] = mapped_column(Boolean, default=False)
    record_outbound: Mapped[bool] = mapped_column(Boolean, default=False)
    record_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)     # 0 = forever
    storage_backend: Mapped[StorageBackend] = mapped_column(Enum(StorageBackend, name="storage_backend_enum"), default=StorageBackend.local)
    storage_path: Mapped[str | None] = mapped_column(String(255))        # local path or remote folder
    storage_credentials: Mapped[str | None] = mapped_column(Text)        # encrypted JSON: token/secret
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CallRecording(Base):
    """Metadata for a recorded call file."""
    __tablename__ = "call_recordings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    cdr_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cdr.id", ondelete="SET NULL"))
    uniqueid: Mapped[str | None] = mapped_column(String(150))            # Asterisk uniqueid
    filename: Mapped[str] = mapped_column(String(255), nullable=False)   # original filename on disk
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    storage_path: Mapped[str | None] = mapped_column(String(500))        # full path/URL in backend
    file_size: Mapped[int | None] = mapped_column(BigInteger)            # bytes
    duration: Mapped[int | None] = mapped_column(Integer)               # seconds
    format: Mapped[str | None] = mapped_column(String(10))              # wav, mp3, ogg
    caller: Mapped[str | None] = mapped_column(String(80))
    callee: Mapped[str | None] = mapped_column(String(80))
    direction: Mapped[str | None] = mapped_column(String(10))           # inbound / outbound / internal
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))   # retention cutoff
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
