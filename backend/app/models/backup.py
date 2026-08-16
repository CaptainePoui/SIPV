"""Backup cloud automatique de notre propre infra SIPV (TASK-S059) -- PAS le
stockage cloud client pour enregistrements d'appel (TASK-S012.1, sujet
distinct). Meme structure que le cote ERPCRM (TASK-035), avec deux
differences propres a SIPV :
- oauth_state vit directement sur CloudBackupConnection (pas d'AppSetting
  generique cote SIPV, contrairement a ERPCRM) -- une seule autorisation en
  vol a la fois par fournisseur, largement suffisant.
- Le flux OAuth est RELAYE par ERPCRM (seul serveur avec domaine public
  joignable par Dropbox/Google) -- voir endpoints/backup.py."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CloudBackupConnection(Base):
    __tablename__ = "cloud_backup_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    account_label: Mapped[str | None] = mapped_column(String(255))
    client_id: Mapped[str | None] = mapped_column(String(255))
    client_secret_enc: Mapped[str | None] = mapped_column(Text)
    oauth_state: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="America/Toronto")
    backup_hour: Mapped[str] = mapped_column(String(5), nullable=False, default="02:00")
    bandwidth_limit_kbps: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BackupCycle(Base):
    __tablename__ = "backup_cycles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frequency_type: Mapped[str] = mapped_column(String(10), nullable=False)
    day_of_week: Mapped[int | None] = mapped_column(Integer)
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    month_of_year: Mapped[int | None] = mapped_column(Integer)
    retention_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    retention_count: Mapped[int] = mapped_column(Integer, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BackupRunLog(Base):
    __tablename__ = "backup_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_manually: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
