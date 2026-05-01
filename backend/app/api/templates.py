from __future__ import annotations

import secrets as secrets_module
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import User, get_current_user
from backend.app.api.services import (
    HealthcheckConfig,
    PortMapping,
    ServiceCreateRequest,
    ServiceCreateResponse,
    VolumeMapping,
    _create_service_sync,
    _record_audit_log,
)
from backend.app.core.service_env import upsert_service_env_entry
from backend.app.db import session_scope
from backend.app.models.service import Service
from backend.app.templates import get_template, list_templates, summarize_template

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateEnvField(BaseModel):
    key: str
    value: str | None = None
    auto_secret: bool = False
    description: str | None = None


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    image: str
    default_resources: dict[str, float]
    ports: list[dict[str, Any]] = Field(default_factory=list)
    volumes: list[dict[str, Any]] = Field(default_factory=list)
    env: list[TemplateEnvField] = Field(default_factory=list)
    healthcheck: dict[str, Any] | None = None
    restart_policy: str = "unless-stopped"
    pids_limit: int | None = None


class TemplateDeployRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cpus: float | None = Field(default=None, gt=0)
    memory_mb: int | None = Field(default=None, gt=0)
    domain: str | None = Field(default=None, max_length=255)
    network: str | None = Field(default=None, max_length=255)
    env_overrides: dict[str, str] = Field(default_factory=dict)


class TemplateDeployResponse(BaseModel):
    template_id: str
    service_id: UUID
    deploy_id: UUID
    status: str
    image: str
    auto_generated_keys: list[str] = Field(default_factory=list)


def _slug_for_name(name: str) -> str:
    slug = "-".join(name.lower().strip().split())
    return "".join(ch for ch in slug if ch.isalnum() or ch == "-").strip("-") or "service"


def _expand_volume_source(source: str, *, slug: str) -> str:
    return source.format(slug=slug)


def _build_request_from_template(
    template: dict[str, Any],
    payload: TemplateDeployRequest,
    *,
    slug_hint: str,
) -> tuple[ServiceCreateRequest, dict[str, str]]:
    """Return (ServiceCreateRequest, auto_secret_values_by_key)."""
    plain_env: dict[str, str] = {}
    auto_secrets: dict[str, str] = {}

    for env_def in template.get("env", []):
        key: str = env_def["key"]
        if env_def.get("auto_secret"):
            override = payload.env_overrides.get(key)
            auto_secrets[key] = override or secrets_module.token_urlsafe(24)
        else:
            override = payload.env_overrides.get(key)
            plain_env[key] = override if override is not None else (env_def.get("value") or "")

    # extra overrides for keys the template did not define
    template_keys = {env["key"] for env in template.get("env", [])}
    for key, value in payload.env_overrides.items():
        if key not in template_keys:
            plain_env[key] = value

    initial_env = {**plain_env, **auto_secrets}

    ports = [PortMapping(**port) for port in template.get("ports", [])]
    volumes = [
        VolumeMapping(
            source=_expand_volume_source(volume["source"], slug=slug_hint),
            target=volume["target"],
            mode=volume.get("mode", "rw"),
        )
        for volume in template.get("volumes", [])
    ]
    healthcheck_payload = template.get("healthcheck")
    healthcheck = HealthcheckConfig(**healthcheck_payload) if healthcheck_payload else None

    defaults = template.get("default_resources", {})
    create_request = ServiceCreateRequest(
        name=payload.name,
        image=template["image"],
        cpus=payload.cpus if payload.cpus is not None else float(defaults.get("cpus", 0.5)),
        memory_mb=payload.memory_mb
        if payload.memory_mb is not None
        else int(defaults.get("memory_mb", 256)),
        env=initial_env,
        ports=ports,
        volumes=volumes,
        network=payload.network,
        domain=payload.domain,
        healthcheck=healthcheck,
        restart_policy=template.get("restart_policy", "unless-stopped"),
        pids_limit=template.get("pids_limit"),
    )
    return create_request, auto_secrets


def _convert_auto_secrets_sync(
    service_id: UUID,
    auto_secrets: dict[str, str],
    template_id: str,
    current_user: User,
) -> None:
    if not auto_secrets:
        return
    with session_scope() as session:
        service = session.get(Service, service_id)
        if service is None:
            return
        for key, value in auto_secrets.items():
            upsert_service_env_entry(session, service, key, value, is_secret=True)
        _record_audit_log(
            session,
            current_user,
            "service.template.deploy",
            service,
            {"template_id": template_id, "auto_secret_keys": sorted(auto_secrets.keys())},
        )
        session.commit()


def _deploy_template_sync(
    template_id: str, payload: TemplateDeployRequest, current_user: User
) -> TemplateDeployResponse:
    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    slug_hint = f"{_slug_for_name(payload.name)}-{str(current_user.id)[:8]}"
    create_request, auto_secrets = _build_request_from_template(
        template, payload, slug_hint=slug_hint
    )

    response: ServiceCreateResponse = _create_service_sync(create_request, current_user)
    _convert_auto_secrets_sync(response.service_id, auto_secrets, template_id, current_user)

    return TemplateDeployResponse(
        template_id=template_id,
        service_id=response.service_id,
        deploy_id=response.deploy_id,
        status=response.status,
        image=response.image,
        auto_generated_keys=sorted(auto_secrets.keys()),
    )


@router.get("", response_model=list[TemplateSummary])
async def get_templates() -> list[TemplateSummary]:
    return [TemplateSummary(**item) for item in list_templates()]


@router.get("/{template_id}", response_model=TemplateSummary)
async def get_template_detail(template_id: str) -> TemplateSummary:
    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return TemplateSummary(**summarize_template(template))


@router.post("/{template_id}/deploy", response_model=TemplateDeployResponse, status_code=status.HTTP_201_CREATED)
async def deploy_template(
    template_id: str,
    payload: TemplateDeployRequest,
    current_user: User = Depends(get_current_user),
) -> TemplateDeployResponse:
    return await run_in_threadpool(_deploy_template_sync, template_id, payload, current_user)
