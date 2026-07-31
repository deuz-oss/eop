from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Operations Platform API"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://eop:eop@postgres:5432/eop"

    redis_url: str = "redis://redis:6379"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
