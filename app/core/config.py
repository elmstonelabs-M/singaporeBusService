from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="Singapore Bus Arrival API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")

    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/bus_app",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    lta_account_key: str = Field(default="", alias="LTA_ACCOUNT_KEY")
    lta_base_url: str = Field(
        default="https://datamall2.mytransport.sg/ltaodataservice",
        alias="LTA_BASE_URL",
    )
    lta_timeout_seconds: float = Field(default=5.0, alias="LTA_TIMEOUT_SECONDS")
    feedback_to_email: str = Field(default="elmstonelabs@gmail.com", alias="FEEDBACK_TO_EMAIL")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    default_arrival_cache_ttl_seconds: int = Field(
        default=20,
        alias="DEFAULT_ARRIVAL_CACHE_TTL_SECONDS",
    )
    default_last_good_cache_ttl_seconds: int = Field(
        default=300,
        alias="DEFAULT_LAST_GOOD_CACHE_TTL_SECONDS",
    )
    default_nearby_cache_ttl_seconds: int = Field(
        default=60,
        alias="DEFAULT_NEARBY_CACHE_TTL_SECONDS",
    )
    default_search_cache_ttl_seconds: int = Field(
        default=86400,
        alias="DEFAULT_SEARCH_CACHE_TTL_SECONDS",
    )
    default_home_cache_ttl_seconds: int = Field(
        default=15,
        alias="DEFAULT_HOME_CACHE_TTL_SECONDS",
    )
    dataset_storage_dir: str = Field(default="datasets", alias="DATASET_STORAGE_DIR")

    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file_path: str | None = Field(default=None, alias="LOG_FILE_PATH")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
