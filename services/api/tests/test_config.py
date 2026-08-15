import pytest
from pydantic import ValidationError

from eop_api.core.config import Settings


def test_settings_defaults():
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.db_pool_size > 0
    assert settings.environment == "development"


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_settings_allows_default_secrets_outside_production():
    settings = Settings(_env_file=None, environment="development")

    assert settings.jwt_secret == "dev-secret-key-change-in-production"
    assert settings.minio_access_key == "minioadmin"
    assert settings.minio_secret_key == "minioadmin"


def test_settings_rejects_default_jwt_secret_in_production():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            environment="production",
            minio_access_key="prod-access-key",
            minio_secret_key="prod-secret-key",
        )


def test_settings_rejects_default_minio_access_key_in_production():
    with pytest.raises(ValidationError, match="MINIO_ACCESS_KEY"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="prod-jwt-secret",
            minio_secret_key="prod-secret-key",
        )


def test_settings_rejects_default_minio_secret_key_in_production():
    with pytest.raises(ValidationError, match="MINIO_SECRET_KEY"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="prod-jwt-secret",
            minio_access_key="prod-access-key",
        )


def test_settings_accepts_production_with_all_secrets_overridden():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="prod-jwt-secret",
        minio_access_key="prod-access-key",
        minio_secret_key="prod-secret-key",
    )

    assert settings.environment == "production"
    assert settings.jwt_secret == "prod-jwt-secret"
    assert settings.minio_access_key == "prod-access-key"
    assert settings.minio_secret_key == "prod-secret-key"
