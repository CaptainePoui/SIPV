import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class VoicemailBox(Base):
    """Voicemail mailbox for an extension."""
    __tablename__ = "voicemail_boxes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    extension_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sip_extensions.id", ondelete="SET NULL"))
    # Asterisk mailbox format: {mailbox}@{context}
    mailbox: Mapped[str] = mapped_column(String(20), nullable=False)  # usually same as extension number
    context: Mapped[str] = mapped_column(String(40), nullable=False, default="default")
    password: Mapped[str] = mapped_column(String(20), nullable=False, default="1234")
    fullname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    pager: Mapped[str | None] = mapped_column(String(100))
    # Email notification settings
    email_on_new: Mapped[bool] = mapped_column(Boolean, default=True)  # send email on new voicemail
    attach_message: Mapped[bool] = mapped_column(Boolean, default=True)  # attach WAV to email
    delete_after_email: Mapped[bool] = mapped_column(Boolean, default=False)
    # Asterisk options
    say_cid: Mapped[bool] = mapped_column(Boolean, default=True)
    say_duration: Mapped[bool] = mapped_column(Boolean, default=True)
    max_messages: Mapped[int] = mapped_column(Integer, default=100)
    max_message_length: Mapped[int] = mapped_column(Integer, default=180)  # seconds
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VoicemailMessage(Base):
    """Voicemail messages (stored in DB for Realtime)."""
    __tablename__ = "voicemail_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("voicemail_boxes.id", ondelete="CASCADE"), nullable=False)
    msgnum: Mapped[int] = mapped_column(Integer, nullable=False)
    folder: Mapped[str] = mapped_column(String(20), default="INBOX")  # INBOX, Old, Work, Family, Friends, Cust1-6
    callerid: Mapped[str | None] = mapped_column(String(100))
    origtime: Mapped[str | None] = mapped_column(String(20))  # Unix timestamp as string
    duration: Mapped[int | None] = mapped_column(Integer)  # seconds
    recording_path: Mapped[str | None] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
