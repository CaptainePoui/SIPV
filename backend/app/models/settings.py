import uuid
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class TelephonySettings(Base):
    """
    Reglages globaux telephonie -- singleton (une seule ligne). Niveau le plus general
    de la chaine d'heritage (Global -> Compagnie -> Poste), voir
    app/core/settings_resolver.py::resolve_setting(). Champs ajoutes au fur et a mesure
    qu'une tache en a reellement besoin (pas de champs speculatifs -- LOI 4).
    """
    __tablename__ = "telephony_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Voicemail global (TASK-S008.2) -- valeur de dernier recours si ni le poste ni la
    # compagnie ne definissent explicitement leur propre valeur (None = herite).
    voicemail_delete_after_email: Mapped[bool] = mapped_column(Boolean, default=False)
    voicemail_max_messages: Mapped[int] = mapped_column(Integer, default=100)
    voicemail_max_message_length: Mapped[int] = mapped_column(Integer, default=300)
    voicemail_language: Mapped[str] = mapped_column(String(5), default="fr")
