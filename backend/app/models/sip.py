import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SIPExtension(Base):
    """SIP endpoint (extension) for a tenant — mirrors ps_endpoints in Asterisk Realtime."""
    __tablename__ = "sip_extensions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # SIP credentials
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # {tenant_account}-{ext}
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Features
    voicemail_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voicemail_email: Mapped[str | None] = mapped_column(String(255))
    caller_id_name: Mapped[str | None] = mapped_column(String(100))
    caller_id_number: Mapped[str | None] = mapped_column(String(30))
    # Call recording
    record_calls: Mapped[bool] = mapped_column(Boolean, default=False)
    # Max channels
    max_contacts: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Liste ordonnee de codecs (meilleur rapport qualite/poids en premier), noms internes
    # ulaw/alaw/g722/g729 -- mappes vers PCMU/PCMA/G722/G729 dans xml_curl.py. Remplace
    # l'ancien champ `codec` (valeur unique) -- TASK-S018.3, decision projet 2026-07-23.
    codec_list: Mapped[str] = mapped_column(String(60), default="ulaw,alaw,g722,g729", server_default="ulaw,alaw,g722,g729")
    # Transport impose pour ce poste — les registrations avec un autre transport sont
    # refusees (verifie via sip_via_protocol dans xml_curl.py _handle_directory)
    transport: Mapped[str] = mapped_column(String(10), default="tls", server_default="tls")  # udp, tcp, tls
    # Horaires — reutilise le Schedule existant (TASK-S016), pas de renvoi hors-heures propre a l'extension
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="SET NULL"))
    # Lien contact ERPCRM (TASK-S022) — pas de FK cross-DB (ERPCRM et SIPV ont des DB separees)
    erpcrm_contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # --- TASK-S018.3 : identification, plan d'appel, renvois, DND ---
    site: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    # Palier d'appel -- local/national/international. ⚠️ PAS ENCORE APPLIQUE par le
    # dialplan (OutboundRoute n'a aucun concept de palier) -- champ stocke + reflete
    # dans le XML directory (toll_allow) mais decoratif tant que TASK-S018.4 (ou
    # equivalent) ne cable pas la verification dans _handle_dialplan.
    call_permission: Mapped[str] = mapped_column(String(20), default="international", server_default="international")
    forward_immediate_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    forward_immediate_destination: Mapped[str | None] = mapped_column(String(100))
    forward_busy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    forward_busy_destination: Mapped[str | None] = mapped_column(String(100))
    forward_no_answer_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    forward_no_answer_destination: Mapped[str | None] = mapped_column(String(100))
    forward_no_answer_delay_seconds: Mapped[int | None] = mapped_column(Integer, default=20)
    forward_offline_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    forward_offline_destination: Mapped[str | None] = mapped_column(String(100))
    dnd_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    dnd_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_answer_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_concurrent_calls: Mapped[int | None] = mapped_column(Integer)
    distinctive_ring: Mapped[str | None] = mapped_column(String(50))
    # Mode d'enregistrement (pertinent seulement si record_calls=True) -- manual = agent
    # declenche via feature code, auto = enregistre systematiquement.
    record_mode: Mapped[str] = mapped_column(String(10), default="manual", server_default="manual")
    # Enregistrement automatique granulaire (TASK-023.4/S018.5, 2026-07-24) -- remplace
    # le choix simple manuel/tout : 4 categories independantes, cablees dans le dialplan
    # (xml_curl.py). record_calls (ci-dessus) reste le declencheur "Manuel" (agent, via
    # P-code Grandstream -- pas encore cable, voir TASK-S011.4).
    record_internal_incoming: Mapped[bool] = mapped_column(Boolean, default=False)
    record_internal_outgoing: Mapped[bool] = mapped_column(Boolean, default=False)
    record_external_incoming: Mapped[bool] = mapped_column(Boolean, default=False)
    record_external_outgoing: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- TASK-S007.2 : pickup/paging/interception (concept poste, pas file d'attente) ---
    pickup_group: Mapped[str | None] = mapped_column(String(50))
    paging_groups: Mapped[str | None] = mapped_column(String(255))  # CSV
    can_intercept_calls: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- TASK-S018.5 : plan d'appel reellement applique (nullable = herite du Tenant) ---
    allow_canada: Mapped[bool | None] = mapped_column(Boolean)
    allow_us: Mapped[bool | None] = mapped_column(Boolean)
    allow_international: Mapped[bool | None] = mapped_column(Boolean)
    allow_premium: Mapped[bool | None] = mapped_column(Boolean)
    blocked_countries: Mapped[str | None] = mapped_column(String(255))  # CSV indicatifs pays (ex: "44,86")
    blocked_prefixes: Mapped[str | None] = mapped_column(String(255))  # CSV prefixes composes a bloquer
    ld_pin: Mapped[str | None] = mapped_column(String(255))  # chiffre (Fernet), code pour outrepasser un blocage
    ld_monthly_limit: Mapped[float | None] = mapped_column(Numeric(10, 2))
    preferred_trunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_trunks.id", ondelete="SET NULL"))

    # Sync state
    freeswitch_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="extensions")

    @property
    def endpoint_name(self) -> str:
        return self.username


class SIPTrunk(Base):
    """SIP trunk connecting to a carrier — mirrors ps_endpoints for trunk in Asterisk."""
    __tablename__ = "sip_trunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(100))
    password: Mapped[str | None] = mapped_column(String(255))
    from_domain: Mapped[str | None] = mapped_column(String(255))
    # Outbound caller ID override
    caller_id: Mapped[str | None] = mapped_column(String(30))
    # Failover trunk
    failover_trunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_trunks.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    freeswitch_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="trunks")


class TenantDID(Base):
    """DID number assigned to a tenant — for inbound routing."""
    __tablename__ = "tenant_dids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(100))
    # Where to route inbound calls
    destination_type: Mapped[str] = mapped_column(String(20), default="extension")  # extension, ivr, queue, voicemail
    destination: Mapped[str | None] = mapped_column(String(100))
    has_911: Mapped[bool] = mapped_column(Boolean, default=False)
    e911_address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="dids")
