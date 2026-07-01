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
    REDIS_URL: str = "redis://localhost:6379/0"
    ASTERISK_ARI_URL: str = "http://localhost:8088"
    ASTERISK_ARI_USER: str = "sipv"
    ASTERISK_ARI_PASSWORD: str = "change_me"

    class Config:
        env_file = ".env"


settings = Settings()
