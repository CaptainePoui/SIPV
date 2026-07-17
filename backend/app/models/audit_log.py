import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)   # extension, trunk, did, tenant, ivr, ...
    entity_id: Mapped[str | None] = mapped_column(String(36))              # UUID de l'objet modifié
    entity_label: Mapped[str | None] = mapped_column(String(200))          # Nom lisible au moment du changement
    action: Mapped[str] = mapped_column(String(20), nullable=False)        # create, update, delete
    old_data: Mapped[dict | None] = mapped_column(JSONB)                   # Snapshot avant
    new_data: Mapped[dict | None] = mapped_column(JSONB)                   # Snapshot après
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)   # Email de l'utilisateur
    changed_by_ip: Mapped[str] = mapped_column(String(45), nullable=False) # IPv4 ou IPv6
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
