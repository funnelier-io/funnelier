"""
Application Configuration
Centralized settings management using pydantic-settings
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "postgresql+asyncpg://funnelier:funnelier@localhost:5433/funnelier"
    pool_size: int = 20
    max_overflow: int = 10
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600  # 1 hour default


class CelerySettings(BaseSettings):
    """Celery task queue settings."""

    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"


class MongoDBSettings(BaseSettings):
    """MongoDB settings for tenant data sources."""

    model_config = SettingsConfigDict(env_prefix="MONGODB_")

    url: str = "mongodb://localhost:27017"
    database: str = "funnelier_tenant"


class JWTSettings(BaseSettings):
    """JWT authentication settings."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: str = "your-jwt-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class KavenegarSettings(BaseSettings):
    """Kavenegar SMS provider settings."""

    model_config = SettingsConfigDict(env_prefix="KAVENEGAR_")

    api_key: str = ""
    sender: str = ""
    enabled: bool = True


class RFMSettings(BaseSettings):
    """RFM segmentation configuration."""

    model_config = SettingsConfigDict(env_prefix="RFM_")

    # Recency thresholds (days)
    recency_score_5: int = 3
    recency_score_4: int = 7
    recency_score_3: int = 14
    recency_score_2: int = 30
    # Anything above 30 days is score 1

    # Frequency thresholds (purchase count)
    frequency_score_5: int = 10
    frequency_score_4: int = 5
    frequency_score_3: int = 3
    frequency_score_2: int = 2
    # 1 purchase is score 1

    # Monetary thresholds (in Rial)
    monetary_score_5: int = 1_000_000_000  # 1B
    monetary_score_4: int = 500_000_000  # 500M
    monetary_score_3: int = 100_000_000  # 100M
    monetary_score_2: int = 50_000_000  # 50M
    # Below 50M is score 1


class FunnelSettings(BaseSettings):
    """Funnel configuration."""

    model_config = SettingsConfigDict(env_prefix="FUNNEL_")

    min_call_duration_seconds: int = 90  # 1.5 minutes
    default_stages: list[str] = [
        "lead_acquired",
        "sms_sent",
        "sms_delivered",
        "call_attempted",
        "call_answered",
        "invoice_issued",
        "payment_received",
    ]


class UploadSettings(BaseSettings):
    """File upload settings."""

    model_config = SettingsConfigDict(env_prefix="UPLOAD_")

    max_size_mb: int = 50
    allowed_extensions: list[str] = ["csv", "xlsx", "xls", "json"]
    temp_directory: str = "/tmp/funnelier/uploads"


class Settings(BaseSettings):
    """
    Main application settings.
    Aggregates all configuration sections.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    env: str = "development"
    debug: bool = True
    secret_key: str = "your-super-secret-key-change-in-production"

    app_name: str = "Funnelier"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate limiting
    rate_limit_requests_per_minute: int = 100

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    mongodb: MongoDBSettings = Field(default_factory=MongoDBSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    kavenegar: KavenegarSettings = Field(default_factory=KavenegarSettings)
    rfm: RFMSettings = Field(default_factory=RFMSettings)
    funnel: FunnelSettings = Field(default_factory=FunnelSettings)
    upload: UploadSettings = Field(default_factory=UploadSettings)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure single instance.
    """
    return Settings()


# Convenience exports
settings = get_settings()
