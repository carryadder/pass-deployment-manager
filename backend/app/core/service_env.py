from __future__ import annotations

from sqlmodel import Session, select

from backend.app.core.secrets import decrypt_secret, encrypt_secret
from backend.app.models.env_var import EnvVar
from backend.app.models.secret import Secret
from backend.app.models.service import Service


def build_service_environment(session: Session, service: Service) -> dict[str, str]:
    runtime_env = dict(service.config.get("env", {}))

    env_vars = session.exec(select(EnvVar).where(EnvVar.service_id == service.id)).all()
    for env_var in env_vars:
        runtime_env[env_var.key] = env_var.value

    secrets = session.exec(select(Secret).where(Secret.service_id == service.id)).all()
    for secret in secrets:
        runtime_env[secret.key] = decrypt_secret(secret.encrypted_value)

    return runtime_env


def list_service_env_entries(session: Session, service: Service) -> list[dict[str, object]]:
    entry_map: dict[str, dict[str, object]] = {}

    for key, value in service.config.get("env", {}).items():
        entry_map[key] = {
            "key": key,
            "value": value,
            "is_secret": False,
            "has_value": True,
        }

    env_vars = session.exec(select(EnvVar).where(EnvVar.service_id == service.id)).all()
    for env_var in env_vars:
        entry_map[env_var.key] = {
            "key": env_var.key,
            "value": env_var.value,
            "is_secret": False,
            "has_value": True,
        }

    secrets = session.exec(select(Secret).where(Secret.service_id == service.id)).all()
    for secret in secrets:
        entry_map[secret.key] = {
            "key": secret.key,
            "value": None,
            "is_secret": True,
            "has_value": True,
        }

    return sorted(entry_map.values(), key=lambda entry: str(entry["key"]).lower())


def persist_service_env(session: Session, service: Service, values: dict[str, str]) -> None:
    for key, value in values.items():
        session.add(
            EnvVar(
                service_id=service.id,
                key=key,
                value=value,
                is_secret=False,
            )
        )


def upsert_service_env_entry(
    session: Session,
    service: Service,
    key: str,
    value: str,
    *,
    is_secret: bool,
) -> dict[str, object]:
    config = dict(service.config)
    config_env = dict(config.get("env", {}))
    config_env.pop(key, None)
    config["env"] = config_env
    service.config = config
    session.add(service)

    existing_env_vars = session.exec(
        select(EnvVar).where(EnvVar.service_id == service.id, EnvVar.key == key)
    ).all()
    for env_var in existing_env_vars:
        session.delete(env_var)

    existing_secrets = session.exec(
        select(Secret).where(Secret.service_id == service.id, Secret.key == key)
    ).all()
    for secret in existing_secrets:
        session.delete(secret)

    if is_secret:
        session.add(
            Secret(
                service_id=service.id,
                key=key,
                encrypted_value=encrypt_secret(value),
            )
        )
        return {"key": key, "value": None, "is_secret": True, "has_value": True}

    session.add(
        EnvVar(
            service_id=service.id,
            key=key,
            value=value,
            is_secret=False,
        )
    )
    return {"key": key, "value": value, "is_secret": False, "has_value": True}


def service_env_entry_exists(session: Session, service: Service, key: str) -> bool:
    if key in service.config.get("env", {}):
        return True

    env_var = session.exec(select(EnvVar).where(EnvVar.service_id == service.id, EnvVar.key == key)).first()
    if env_var is not None:
        return True

    secret = session.exec(select(Secret).where(Secret.service_id == service.id, Secret.key == key)).first()
    return secret is not None


def delete_service_env_entry(session: Session, service: Service, key: str) -> bool:
    deleted = False
    config = dict(service.config)
    config_env = dict(config.get("env", {}))
    if key in config_env:
        config_env.pop(key, None)
        config["env"] = config_env
        service.config = config
        session.add(service)
        deleted = True

    env_vars = session.exec(select(EnvVar).where(EnvVar.service_id == service.id, EnvVar.key == key)).all()
    for env_var in env_vars:
        session.delete(env_var)
        deleted = True

    secrets = session.exec(select(Secret).where(Secret.service_id == service.id, Secret.key == key)).all()
    for secret in secrets:
        session.delete(secret)
        deleted = True

    return deleted


__all__ = [
    "build_service_environment",
    "delete_service_env_entry",
    "list_service_env_entries",
    "persist_service_env",
    "service_env_entry_exists",
    "upsert_service_env_entry",
]
