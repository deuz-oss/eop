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
