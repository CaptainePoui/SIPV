from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sipv:sipv_change_me@localhost:5432/sipv"
    SECRET_KEY: str = "change_me_to_a_very_long_random_string"
    ENVIRONMENT: str = "development"
    # Network — change these when migrating servers
    SIPV_HOST: str = "192.168.1.55"
    ERPCRM_HOST: str = "192.168.1.9"
    ERPCRM_API_URL: str = "http://192.168.1.9:8010"
    ERPCRM_API_KEY: str = ""
    # FreeSWITCH ESL (Event Socket Library)
    FREESWITCH_HOST: str = "127.0.0.1"
    FREESWITCH_ESL_PORT: int = 8021
    FREESWITCH_ESL_PASSWORD: str = "ClueCon"

    class Config:
        env_file = ".env"


settings = Settings()
