import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class IVR(Base):
    """Interactive Voice Response menu."""
    __tablename__ = "ivrs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    greeting_text: Mapped[str | None] = mapped_column(Text)  # TTS or filename
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    invalid_destination: Mapped[str | None] = mapped_column(String(100))  # where to send on invalid input
    timeout_destination: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    options: Mapped[list["IVROption"]] = relationship("IVROption", back_populates="ivr", cascade="all, delete-orphan")


class IVROption(Base):
    """A single digit option in an IVR menu."""
    __tablename__ = "ivr_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ivr_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ivrs.id", ondelete="CASCADE"), nullable=False)
    digit: Mapped[str] = mapped_column(String(5), nullable=False)  # 0-9, *, #
    label: Mapped[str | None] = mapped_column(String(100))
    destination_type: Mapped[str] = mapped_column(String(20), nullable=False)  # extension, queue, ivr, voicemail
    destination: Mapped[str] = mapped_column(String(100), nullable=False)

    ivr: Mapped["IVR"] = relationship("IVR", back_populates="options")


class Queue(Base):
    """Call queue (ACD queue)."""
    __tablename__ = "queues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Internal queue name for Asterisk: {tenant_account}_queue_{name}
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    strategy: Mapped[str] = mapped_column(String(20), default="rrmemory")  # ringall, leastrecent, fewestcalls, rrmemory, random
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    # Where to send if no agent answers
    no_answer_destination: Mapped[str | None] = mapped_column(String(100))
    max_wait_seconds: Mapped[int] = mapped_column(Integer, default=120)
    announce_hold_time: Mapped[bool] = mapped_column(Boolean, default=True)
    music_on_hold: Mapped[str] = mapped_column(String(50), default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    members: Mapped[list["QueueMember"]] = relationship("QueueMember", back_populates="queue", cascade="all, delete-orphan")


class QueueMember(Base):
    """Agent/member in a call queue."""
    __tablename__ = "queue_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    extension_username: Mapped[str] = mapped_column(String(100), nullable=False)
    # "Niveau de priorite" (TASK-S007.2) = ce champ deja existant, pas duplique --
    # plus bas = priorite plus haute (convention standard queue ACD).
    penalty: Mapped[int] = mapped_column(Integer, default=0)

    # --- TASK-S007.2 : champs agent ---
    agent_number: Mapped[str | None] = mapped_column(String(20))
    agent_password: Mapped[str | None] = mapped_column(String(50))  # pas chiffre -- meme
    # convention que SIPExtension.password (valeur active necessaire au systeme, pas
    # juste consultable par un humain).
    is_dynamic: Mapped[bool] = mapped_column(Boolean, default=True)  # dynamique = agent peut se logguer/se delogguer
    auto_login: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    pause_reasons: Mapped[str | None] = mapped_column(String(255))  # CSV, ex: "Diner,Pause,Reunion"
    wrap_up_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    skills: Mapped[str | None] = mapped_column(String(255))  # CSV
    # --- TASK-023.10 : memes limites que le reste du module queue -- stockes/
    # editables mais PAS encore pousses vers mod_callcenter (aucun champ de Queue/
    # QueueMember ne l'est, voir TASK-S007.2 "rien ne pousse jamais les queues/agents
    # vers le runtime") ---
    ring_even_if_busy: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_multiple_queue_calls: Mapped[bool] = mapped_column(Boolean, default=False)

    queue: Mapped["Queue"] = relationship("Queue", back_populates="members")


class RingGroup(Base):
    """Ring group — rings multiple extensions simultaneously or sequentially."""
    __tablename__ = "ring_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)  # The extension number to call this group
    ring_strategy: Mapped[str] = mapped_column(String(20), default="simultaneous")  # simultaneous, hunt
    ring_time: Mapped[int] = mapped_column(Integer, default=20)
    # ⚠️ LEGACY (TASK-023.9) : source de verite avant cette tache. Remplace par la
    # table ring_group_members (priorite/ordre/exclusion par poste) -- conserve tel
    # quel pour compat/historique, plus lu par le dialplan (_ringgroup_dialplan_entries).
    members: Mapped[str] = mapped_column(Text, nullable=False)  # comma-separated extension usernames
    no_answer_destination: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # --- TASK-023.9 ---
    confirm_before_answer: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="SET NULL"))

    ring_members: Mapped[list["RingGroupMember"]] = relationship("RingGroupMember", back_populates="ring_group", cascade="all, delete-orphan")


class RingGroupMember(Base):
    """Membre d'un groupe d'appel avec priorite/ordre/exclusion temporaire (TASK-023.9)."""
    __tablename__ = "ring_group_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ring_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ring_groups.id", ondelete="CASCADE"), nullable=False)
    extension_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_extensions.id", ondelete="CASCADE"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # plus bas = priorite plus haute (meme convention que QueueMember.penalty)
    ring_order: Mapped[int] = mapped_column(Integer, default=0)  # ordre de sonnerie pour la strategie "hunt" (sequentielle)
    temporarily_excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    ring_group: Mapped["RingGroup"] = relationship("RingGroup", back_populates="ring_members")
    extension: Mapped["SIPExtension"] = relationship("SIPExtension")


class ParkingLot(Base):
    """Call parking lot configuration per tenant."""
    __tablename__ = "parking_lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    park_extension: Mapped[str] = mapped_column(String(10), nullable=False, default="700")
    parking_slots_start: Mapped[int] = mapped_column(Integer, default=701)
    parking_slots_end: Mapped[int] = mapped_column(Integer, default=720)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    return_extension: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
