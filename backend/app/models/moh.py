import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class MohFile(Base):
    """
    TASK-S033 (musique d'attente) : bibliothèque de fichiers MOH. `tenant_id`
    NULL = fichier global, disponible pour TOUS les tenants (option demandée
    explicitement : uploader dans Serveur sans attribuer à un tenant = visible
    partout via le filtre côté compagnie). `tenant_id` rempli = dédié à ce
    tenant seulement.
    """
    __tablename__ = "moh_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TenantMohSelection(Base):
    """
    Sélection multiple d'un tenant parmi les MohFile disponibles (globaux +
    dédiés à lui) -- demande explicite : "il faut que je puisse en
    sélectionner plusieurs". `sort_order` détermine l'ordre dans le fichier
    local_stream généré (voir xml_curl.py::_regenerate_local_stream_conf).
    """
    __tablename__ = "tenant_moh_selections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    moh_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("moh_files.id", ondelete="CASCADE"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
