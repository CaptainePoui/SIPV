from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sipv:sipv_change_me@localhost:5432/sipv"
    SECRET_KEY: str = "change_me_to_a_very_long_random_string"
    ENVIRONMENT: str = "development"
    # Network — change these when migrating servers
    SIPV_HOST: str = "192.168.1.55"
    SIPV_PUBLIC_IP: str = "142.112.42.52"  # IP publique -- utilisee comme outbound proxy pour les postes (fonctionne local + distant via hairpin NAT)
    ERPCRM_HOST: str = "192.168.1.9"
    ERPCRM_API_URL: str = "https://192.168.1.9:8011"
    ERPCRM_API_KEY: str = ""  # cle que ERPCRM doit presenter en X-Api-Key pour appeler SIPV (/sync/company)
    SIPV_API_KEY: str = ""  # cle que SIPV doit presenter en X-Api-Key pour appeler ERPCRM (/contacts, /sipv/event)
    # FreeSWITCH ESL (Event Socket Library)
    FREESWITCH_HOST: str = "127.0.0.1"
    FREESWITCH_ESL_PORT: int = 8021
    FREESWITCH_ESL_PASSWORD: str = "ClueCon"
    # Backup cloud infra (TASK-S059) -- fallback si la connexion n'a pas ses
    # propres credentials saisis dans Admin/Serveur (voir
    # backup_cloud.resolve_credentials). Optionnel, Philippe entre ses
    # propres cles Dropbox/Google pour SIPV via l'UI la plupart du temps.
    DROPBOX_CLIENT_ID: str = ""
    DROPBOX_CLIENT_SECRET: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Seul ERPCRM a un domaine public joignable par Dropbox/Google -- le flux
    # OAuth du backup SIPV est donc relaye via ERPCRM (voir endpoints/backup.py
    # cote SIPV + server.py cote ERPCRM).
    ERPCRM_PUBLIC_BASE_URL: str = "https://portail.simpleip.tel"

    class Config:
        env_file = ".env"


settings = Settings()
