"""Application configuration, driven by environment variables."""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    APP_NAME: str = "Telecom SaaS Platform"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/telecom"
    )

    # --- Dev-only DB bootstrap (NEVER honored in production) ---
    DEV_AUTO_CREATE_DB: bool = False
    DEV_AUTO_SEED: bool = False
    DEV_SEED_ADMIN_EMAIL: str = "admin@platform.local"
    DEV_SEED_ADMIN_PASSWORD: str = "ChangeMe123!"

    # --- JWT / Security ---
    JWT_SECRET_KEY: str = Field(default="CHANGE_ME_IN_PRODUCTION")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    INVITE_TOKEN_EXPIRE_MINUTES: int = 4320  # 72h
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # --- Email / SMTP ---
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@telecom.local"
    SMTP_USE_TLS: bool = True
    FRONTEND_BASE_URL: str = "http://localhost:4200"

    # --- Password policy ---
    PASSWORD_MIN_LENGTH: int = 10
    BCRYPT_ROUNDS: int = 12

    # --- Account lockout ---
    MAX_FAILED_LOGINS: int = 5

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:4200"]

    # --- File storage ---
    UPLOAD_DIR: str = "uploads"
    UPLOAD_URL_BASE: str = "/uploads"
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024  # 2 MB

    # --- Telephony / Asterisk ---
    TELEPHONY_PROVIDER: str = "null"
    TELEPHONY_CONNECT_TIMEOUT: int = 5

    # --- Kafka (platform event bus) ---
    # Set to a real broker address to enable async processing.
    # With "localhost:9092" (default) and no broker running, the producer
    # falls back to NullProducer mode (logs messages, no network I/O).
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False  # flip to True once Kafka is running

    # --- SMS Forwarding API ---
    # The standalone microservice that communicates with AkashSMS gateway.
    # The platform NEVER contacts AkashSMS directly — only via this API.
    SMS_FORWARDING_API_URL: str = "http://localhost:8001"
    SMS_FORWARDING_API_KEY: str = ""

    # --- SMS Provider ---
    # "null" = NullSmsProvider (simulation, default — no SMS sent).
    # "akashsms" = AkashSmsProvider (calls SMS Forwarding API).
    # Switch to "akashsms" once the Forwarding API is running.
    SMS_PROVIDER: str = "null"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_must_be_set_in_prod(cls, v: str, info) -> str:
        env = (info.data or {}).get("ENVIRONMENT", "development")
        if env == "production" and v == "CHANGE_ME_IN_PRODUCTION":
            raise ValueError("JWT_SECRET_KEY must be set in production")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton; overridable in tests via dependency_overrides."""
    return Settings()


settings = get_settings()
