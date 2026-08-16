from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "dev-secret-key-change-in-production"
_DEFAULT_MINIO_ACCESS_KEY = "minioadmin"
_DEFAULT_MINIO_SECRET_KEY = "minioadmin"


class Settings(BaseSettings):
    app_name: str = "Enterprise Operations Platform API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://eop:eop@postgres:5432/eop"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    redis_url: str = "redis://redis:6379"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = _DEFAULT_MINIO_ACCESS_KEY
    minio_secret_key: str = _DEFAULT_MINIO_SECRET_KEY
    minio_secure: bool = False
    minio_bucket: str = "eop-files"

    file_upload_max_size_bytes: int = 10 * 1024 * 1024

    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def _reject_development_defaults_in_production(self) -> Self:
        """Refuses to construct `Settings` for `environment="production"` if any
        of the JWT signing secret or MinIO credentials are still at their
        publicly-known development default -- these values are visible in this
        repository's source, so leaving them unset in production is equivalent
        to having no authentication/storage credentials at all."""
        if self.environment != "production":
            return self

        insecure_fields = []
        if self.jwt_secret == _DEFAULT_JWT_SECRET:
            insecure_fields.append("JWT_SECRET")
        if self.minio_access_key == _DEFAULT_MINIO_ACCESS_KEY:
            insecure_fields.append("MINIO_ACCESS_KEY")
        if self.minio_secret_key == _DEFAULT_MINIO_SECRET_KEY:
            insecure_fields.append("MINIO_SECRET_KEY")

        if insecure_fields:
            raise ValueError(
                "Refusing to start with environment=production while these settings "
                f"still hold development default values: {', '.join(insecure_fields)}. "
                "Set them via environment variables before deploying to production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
