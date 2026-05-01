from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Deployment Manager"
    app_env: str = "development"
    app_debug: bool = True
    docker_host: str | None = None
    database_url: str = (
        "postgresql+psycopg://deployment_manager:deployment_manager@localhost:5432/"
        "deployment_manager"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
