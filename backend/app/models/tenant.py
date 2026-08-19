import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, Numeric, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
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
    # Serveur SIPV qui heberge ce tenant (TASK-S042) -- nullable pour l'instant
    # (un seul serveur existe, tous les tenants y pointent apres backfill), pret
    # pour un futur dispatcheur central quand un 2e serveur sera provisionne.
    server_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sipv_servers.id", ondelete="SET NULL"))
    max_extensions: Mapped[int] = mapped_column(Integer, default=10)
    max_trunks: Mapped[int] = mapped_column(Integer, default=2)
    notes: Mapped[str | None] = mapped_column(Text)
    # Override compagnie du reglage voicemail global (TASK-S008.2) -- null = herite du
    # niveau global (TelephonySettings). Meme nom de champ que sur VoicemailBox et
    # TelephonySettings pour que resolve_setting() fonctionne par simple getattr.
    voicemail_delete_after_email: Mapped[bool | None] = mapped_column(Boolean)

    # --- TASK-S018.5 : defauts compagnie du plan d'appel (base de la chaine
    # d'heritage -- SIPExtension.allow_* herite d'ici quand null) ---
    default_allow_canada: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    default_allow_us: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    default_allow_international: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    default_allow_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    default_blocked_countries: Mapped[str | None] = mapped_column(String(255))
    default_blocked_prefixes: Mapped[str | None] = mapped_column(String(255))
    default_ld_pin: Mapped[str | None] = mapped_column(String(255))  # chiffre (Fernet)
    default_ld_monthly_limit: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # --- TASK-018.6 : caller ID externe par defaut de la compagnie ---
    default_caller_id_name: Mapped[str | None] = mapped_column(String(100))
    default_caller_id_number: Mapped[str | None] = mapped_column(String(30))

    # TASK-S033.2 : ordre de lecture du MOH -- true = aleatoire (mod_local_stream
    # "shuffle", comportement historique/defaut), false = liste dans l'ordre
    # choisi (TenantMohSelection.sort_order). Demande explicite : les deux
    # options doivent etre disponibles, pas juste toujours aleatoire.
    moh_shuffle: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Valeurs par defaut du catalogue d'options telephonie (TASK-S011.5), niveau
    # compagnie -- cle/valeur du catalogue (ex: {"language": "fr"}). Un poste
    # (ProvisionedPhone.extra_config) peut ecraser une cle precise pour lui seul ;
    # une cle absente ici et absente du poste retombe sur le defaut systeme.
    phone_option_defaults: Mapped[dict | None] = mapped_column(JSON)
    # TASK-S044.2 -- PLUSIEURS templates de tenant choisis explicitement
    # (bibliotheque partagee TenantTemplate, creee dans Serveur), fusionnes
    # dans l'ordre du tableau (le dernier gagne en cas de cle en commun).
    # Tableau vide = aucun, la chaine d'heritage saute ce niveau. Pas de FK
    # Postgres sur les elements du tableau -- integrite geree cote application,
    # meme esprit que blocked_countries/blocked_prefixes deja dans ce modele.
    selected_tenant_template_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")
    # TASK-S044.2 -- Global Templates supplementaires choisis explicitement par
    # cette compagnie, en PLUS de celui marque is_default (qui reste applique
    # automatiquement, "policy"). Fusionnes apres le is_default, avant
    # phone_option_defaults.
    selected_global_template_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")

    # TASK-032.2 (TASKERPCRM.md) -- retention CDR en jours, 1 an par defaut.
    # Augmentable manuellement par Philippe si un client paie pour la ressource
    # (pas de logique de facturation ajoutee ici, juste le champ).
    cdr_retention_days: Mapped[int] = mapped_column(Integer, default=365, server_default="365")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    extensions: Mapped[list["SIPExtension"]] = relationship("SIPExtension", back_populates="tenant", cascade="all, delete-orphan")
    trunks: Mapped[list["SIPTrunk"]] = relationship("SIPTrunk", back_populates="tenant", cascade="all, delete-orphan")
    dids: Mapped[list["TenantDID"]] = relationship("TenantDID", back_populates="tenant", cascade="all, delete-orphan")
    server: Mapped["SipvServer | None"] = relationship("SipvServer")
