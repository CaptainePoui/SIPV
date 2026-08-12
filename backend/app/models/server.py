import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SipvServer(Base):
    """Un serveur FreeSWITCH SIPV physique/virtuel. Un seul aujourd'hui, mais les
    tenants y referent deja (Tenant.server_id) pour que l'ajout d'un 2e serveur
    plus tard ne demande pas de retrofit sur les tenants/DID existants -- le
    dispatcheur central ("classe 4") lui-meme reste a construire quand un 2e
    serveur sera reellement provisionne (TASK-S042)."""
    __tablename__ = "sipv_servers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    # TASK-S054 -- fournisseur SIP exige 2 IP publiques distinctes pour les
    # canaux (une pour les appels entrants, une pour les sortants). Champs de
    # reference/configuration seulement pour l'instant -- PAS encore appliques
    # au binding reseau reel de FreeSWITCH (external_sip_ip, ACL TASK-S050) ni
    # a aucune config trunk : l'utilisateur ne connait pas encore ces IP,
    # a confirmer avec son fournisseur avant toute application reelle.
    sip_inbound_ip: Mapped[str | None] = mapped_column(String(45))
    sip_outbound_ip: Mapped[str | None] = mapped_column(String(45))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
