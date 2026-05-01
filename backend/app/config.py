from functools import lru_cache
from pathlib import Path

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
    jwt_secret_key: str = "change-me"
    jwt_refresh_secret_key: str = "change-me-too"
    fernet_secret_key: str = "change-me-fernet"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_full_name: str = "Bootstrap Admin"
    deploy_workspace: Path = Path(".dmgr-workspace")
    metrics_sample_interval_seconds: int = 5
    metrics_max_samples: int = 60
    traefik_public_network: str = "dmgr-public"
    traefik_cert_resolver: str = "letsencrypt"
    traefik_web_entrypoint: str = "web"
    traefik_websecure_entrypoint: str = "websecure"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
