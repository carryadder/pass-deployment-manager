from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import User, get_current_user
from backend.app.db import session_scope
from backend.app.models.audit_log import AuditLog
from backend.app.models.deploy import Deploy
from backend.app.models.env_var import EnvVar
from backend.app.models.project import Project
from backend.app.models.secret import Secret
from backend.app.models.service import Service
from backend.app.core.lifecycle import (
    restart_container,
    start_container,
    stop_container,
    remove_container,
)
from backend.app.core.metrics import metrics_sampler, parse_metrics_range
from backend.app.core.runner import DockerException, run_service
from backend.app.core.runner import get_service_container_by_slug
from backend.app.core.service_env import (
    delete_service_env_entry,
    list_service_env_entries,
    persist_service_env,
    service_env_entry_exists,
    upsert_service_env_entry,
)
from backend.app.core.traefik import TraefikConfigError, build_service_routing
from backend.app.workers.tasks import enqueue_deploy_job, enqueue_rollout_job, get_deploy_logs

router = APIRouter(prefix="/api/services", tags=["services"])


class PortMapping(BaseModel):
    container_port: int = Field(gt=0, le=65535)
    host_port: int | None = Field(default=None, gt=0, le=65535)


class VolumeMapping(BaseModel):
    source: str = Field(min_length=1, max_length=255)
    target: str = Field(min_length=1, max_length=255)
    mode: str = Field(default="rw", pattern="^(ro|rw)$")


class HealthcheckConfig(BaseModel):
    type: str = Field(pattern="^(http|tcp|cmd)$")
    value: str = Field(min_length=1, max_length=1000)
    interval_seconds: int = Field(default=10, ge=1, le=300)
    timeout_seconds: int = Field(default=3, ge=1, le=300)
    start_period_seconds: int = Field(default=5, ge=0, le=300)
    retries: int = Field(default=3, ge=1, le=20)


class ServiceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    image: str = Field(min_length=1, max_length=500)
    cpus: float = Field(gt=0)
    memory_mb: int = Field(gt=0)
    disk_mb: int | None = Field(default=None, gt=0)
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[PortMapping] = Field(default_factory=list)
    volumes: list[VolumeMapping] = Field(default_factory=list)
    network: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    healthcheck: HealthcheckConfig | None = None
    restart_policy: str = Field(default="unless-stopped", max_length=50)
    pids_limit: int | None = Field(default=256, gt=0)

    @field_validator("restart_policy")
    @classmethod
    def validate_restart_policy(cls, value: str) -> str:
        allowed = {"no", "always", "unless-stopped", "on-failure"}
        if value not in allowed:
            raise ValueError(f"restart_policy must be one of: {', '.join(sorted(allowed))}")
        return value


class ServiceCreateResponse(BaseModel):
    service_id: UUID
    deploy_id: UUID
    status: str
    container_id: str
    container_name: str | None
    image: str
    project_id: UUID


class ServiceDeployRequest(BaseModel):
    git_url: str = Field(min_length=1, max_length=1000)
    branch: str | None = Field(default=None, max_length=255)
    commit: str | None = Field(default=None, max_length=64)
    dockerfile_path: str | None = Field(default=None, max_length=500)
    build_args: dict[str, str] = Field(default_factory=dict)


class DeployResponse(BaseModel):
    deploy_id: UUID
    service_id: UUID
    status: str
    source_type: str
    source_ref: str | None
    image_tag: str | None

    @classmethod
    def from_model(cls, deploy: Deploy) -> "DeployResponse":
        return cls(
            deploy_id=deploy.id,
            service_id=deploy.service_id,
            status=deploy.status,
            source_type=deploy.source_type,
            source_ref=deploy.source_ref,
            image_tag=deploy.image_tag,
        )


class DeployLogsResponse(BaseModel):
    deploy_id: UUID
    lines: list[str]


class RollbackResponse(BaseModel):
    deploy_id: UUID
    status: str
    image_tag: str


class ServiceEnvEntry(BaseModel):
    key: str
    value: str | None = None
    is_secret: bool
    has_value: bool = True


class ServiceEnvUpsertRequest(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    value: str = Field(max_length=4000)
    is_secret: bool = False
    apply: bool = True


class ServiceEnvUpdateRequest(BaseModel):
    value: str = Field(max_length=4000)
    is_secret: bool | None = None
    apply: bool = True


class ServiceEnvMutationResponse(BaseModel):
    entry: ServiceEnvEntry
    applied: bool
    deploy_id: UUID | None = None
    service_status: str


class ServiceEnvDeleteResponse(BaseModel):
    key: str
    deleted: bool
    applied: bool
    deploy_id: UUID | None = None
    service_status: str


class ServiceMetricSample(BaseModel):
    timestamp: str
    cpu_percent: float
    memory_usage_bytes: int
    memory_limit_bytes: int
    memory_percent: float
    network_rx_bytes: int
    network_tx_bytes: int
    block_read_bytes: int
    block_write_bytes: int
    pids: int


class ServiceListItem(BaseModel):
    service_id: UUID
    name: str
    slug: str
    image: str
    status: str
    project_id: UUID
    created_at: str
    updated_at: str
    domain: str | None = None
    ports: list[dict] = Field(default_factory=list)
    uptime_seconds: float | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None


class ServiceActionResponse(BaseModel):
    service_id: UUID
    status: str
    container_id: str | None = None
    action: str


def _slugify(name: str) -> str:
    slug = "-".join(name.lower().strip().split())
    return "".join(ch for ch in slug if ch.isalnum() or ch == "-").strip("-") or "service"


def _ensure_default_project(session, user: User) -> Project:
    default_slug = f"{_slugify(user.full_name)}-{str(user.id)[:8]}"
    project = session.exec(select(Project).where(Project.owner_id == user.id)).first()
    if project is not None:
        return project

    project = Project(
        name=f"{user.full_name} Project",
        slug=default_slug,
        owner_id=user.id,
        description="Default personal project created automatically.",
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def _get_service_or_404(session, service_id: UUID) -> Service:
    service = session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def _ensure_service_access(service: Service, current_user: User, detail: str) -> None:
    if service.project is not None and service.project.owner_id != current_user.id and not current_user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _record_audit_log(session, actor: User, action: str, service: Service, details: dict) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            resource_type="service",
            resource_id=str(service.id),
            details=details,
        )
    )


def _queue_env_apply(session, service: Service, current_user: User, source_ref: str) -> Deploy:
    deploy = Deploy(
        service_id=service.id,
        status="queued",
        source_type="env_update",
        source_ref=source_ref,
        image_tag=service.image,
    )
    service.status = "env_update_queued"
    session.add(deploy)
    session.add(service)
    session.flush()
    _record_audit_log(
        session,
        current_user,
        "service.env.apply",
        service,
        {"source_ref": source_ref, "deploy_id": str(deploy.id)},
    )
    return deploy


def _service_uptime_seconds(service) -> float | None:
    container = get_service_container_by_slug(service.slug)
    if container is None:
        return None
    started_at = container.attrs.get("State", {}).get("StartedAt")
    if not started_at or started_at.startswith("0001-01-01"):
        return None
    try:
        normalized = started_at.replace("Z", "+00:00")
        from datetime import datetime, timezone

        started = datetime.fromisoformat(normalized)
        return max((datetime.now(timezone.utc) - started).total_seconds(), 0.0)
    except ValueError:
        return None


def _latest_metrics(service_id: UUID) -> tuple[float | None, float | None]:
    history = metrics_sampler.get_history(service_id, "5m")
    if not history:
        return None, None
    latest = history[-1]
    return latest.get("cpu_percent"), latest.get("memory_percent")


def _create_service_sync(payload: ServiceCreateRequest, current_user: User) -> ServiceCreateResponse:
    with session_scope() as session:
        project = _ensure_default_project(session, current_user)
        service_slug = f"{_slugify(payload.name)}-{str(current_user.id)[:8]}"
        service_config = payload.model_dump()
        base_labels = {
            "dmgr.service.slug": service_slug,
            "dmgr.project.id": str(project.id),
            "dmgr.owner.id": str(current_user.id),
        }
        try:
            routing = build_service_routing(
                service_slug=service_slug,
                domain=payload.domain,
                ports=service_config.get("ports", []),
                requested_network=payload.network,
                base_labels=base_labels,
            )
        except TraefikConfigError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        runner_payload = {
            **service_config,
            "name": service_slug,
            "labels": routing["labels"],
            "network": routing["network"],
            "extra_networks": routing["extra_networks"],
        }

        try:
            container = run_service(runner_payload)
        except DockerException as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        service = Service(
            name=payload.name,
            slug=service_slug,
            image=payload.image,
            status="running",
            project_id=project.id,
            config={
                **{**service_config, "env": {}},
                "current_container_name": service_slug,
                "previous_image": None,
                "last_successful_deploy_id": None,
            },
        )
        deploy = Deploy(
            service_id=service.id,
            status="running",
            source_type="image",
            source_ref=payload.image,
            image_tag=payload.image,
        )

        session.add(service)
        session.add(deploy)
        persist_service_env(session, service, payload.env)
        _record_audit_log(
            session,
            current_user,
            "service.create",
            service,
            {"image": payload.image, "domain": payload.domain, "project_id": str(project.id)},
        )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Service slug already exists") from exc
        session.refresh(service)
        session.refresh(deploy)

        return ServiceCreateResponse(
            service_id=service.id,
            deploy_id=deploy.id,
            status=service.status,
            container_id=container.get("Id", ""),
            container_name=container.get("Name"),
            image=service.image,
            project_id=project.id,
        )


@router.post("", response_model=ServiceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ServiceCreateResponse:
    return await run_in_threadpool(_create_service_sync, payload, current_user)


def _list_services_sync(current_user: User) -> list[ServiceListItem]:
    with session_scope() as session:
        statement = select(Service)
        if not current_user.is_owner:
            statement = statement.join(Project).where(Project.owner_id == current_user.id)

        services = session.exec(statement.order_by(Service.created_at.desc())).all()
        items: list[ServiceListItem] = []
        for service in services:
            cpu_percent, memory_percent = _latest_metrics(service.id)
            items.append(
                ServiceListItem(
                    service_id=service.id,
                    name=service.name,
                    slug=service.slug,
                    image=service.image,
                    status=service.status,
                    project_id=service.project_id,
                    created_at=service.created_at.isoformat(),
                    updated_at=service.updated_at.isoformat(),
                    domain=service.config.get("domain"),
                    ports=service.config.get("ports", []),
                    uptime_seconds=_service_uptime_seconds(service),
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                )
            )
        return items


@router.get("", response_model=list[ServiceListItem])
async def list_services(current_user: User = Depends(get_current_user)) -> list[ServiceListItem]:
    return await run_in_threadpool(_list_services_sync, current_user)


def _deploy_service_from_git_sync(
    service_id: UUID, payload: ServiceDeployRequest, current_user: User
) -> DeployResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to deploy this service")

        deploy = Deploy(
            service_id=service.id,
            status="queued",
            source_type="git",
            source_ref=payload.git_url,
        )
        service.status = "build_queued"
        session.add(deploy)
        session.add(service)
        session.commit()
        session.refresh(deploy)

        enqueue_deploy_job(
            deploy_id=deploy.id,
            service_id=service.id,
            git_url=payload.git_url,
            branch=payload.branch,
            commit=payload.commit,
            dockerfile_path=payload.dockerfile_path,
            build_args=payload.build_args,
        )
        return DeployResponse.from_model(deploy)


@router.post("/{service_id}/deploy", response_model=DeployResponse, status_code=status.HTTP_202_ACCEPTED)
async def deploy_service_from_git(
    service_id: UUID,
    payload: ServiceDeployRequest,
    current_user: User = Depends(get_current_user),
) -> DeployResponse:
    return await run_in_threadpool(_deploy_service_from_git_sync, service_id, payload, current_user)


def _act_on_service_container_sync(service_id: UUID, current_user: User, action: str) -> ServiceActionResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to modify this service")

        container = get_service_container_by_slug(service.slug)
        if container is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found for service")

        if action == "start":
            attrs = start_container(container.id)
            service.status = "running"
        elif action == "stop":
            attrs = stop_container(container.id)
            service.status = "stopped"
        elif action == "restart":
            attrs = restart_container(container.id)
            service.status = "running"
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported service action")

        _record_audit_log(
            session,
            current_user,
            f"service.{action}",
            service,
            {"container_id": container.id},
        )
        session.add(service)
        session.commit()
        return ServiceActionResponse(
            service_id=service.id,
            status=service.status,
            container_id=attrs.get("Id"),
            action=action,
        )


@router.post("/{service_id}/start", response_model=ServiceActionResponse)
async def start_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> ServiceActionResponse:
    return await run_in_threadpool(_act_on_service_container_sync, service_id, current_user, "start")


@router.post("/{service_id}/stop", response_model=ServiceActionResponse)
async def stop_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> ServiceActionResponse:
    return await run_in_threadpool(_act_on_service_container_sync, service_id, current_user, "stop")


@router.post("/{service_id}/restart", response_model=ServiceActionResponse)
async def restart_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> ServiceActionResponse:
    return await run_in_threadpool(_act_on_service_container_sync, service_id, current_user, "restart")


def _redeploy_service_sync(service_id: UUID, current_user: User) -> RollbackResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to redeploy this service")

        deploy = Deploy(
            service_id=service.id,
            status="queued",
            source_type="redeploy",
            source_ref=service.image,
            image_tag=service.image,
        )
        service.status = "redeploy_queued"
        session.add(deploy)
        session.add(service)
        session.commit()
        session.refresh(deploy)

        enqueue_rollout_job(deploy.id, service.id, service.image)
        return RollbackResponse(deploy_id=deploy.id, status=deploy.status, image_tag=service.image)


@router.post("/{service_id}/redeploy", response_model=RollbackResponse, status_code=status.HTTP_202_ACCEPTED)
async def redeploy_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> RollbackResponse:
    return await run_in_threadpool(_redeploy_service_sync, service_id, current_user)


def _rollout_built_service_sync(service_id: UUID, current_user: User) -> DeployResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to deploy this service")

        deploy = session.exec(
            select(Deploy).where(Deploy.service_id == service_id).order_by(Deploy.created_at.desc())
        ).first()
        if deploy is None or deploy.image_tag is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No built deploy is available for rollout")
        if deploy.status not in {"built", "rollout_failed"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Latest deploy is not ready for rollout")

        enqueue_rollout_job(deploy.id, service.id, deploy.image_tag)
        return DeployResponse.from_model(deploy)


@router.post("/{service_id}/rollout", response_model=DeployResponse, status_code=status.HTTP_202_ACCEPTED)
async def rollout_built_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> DeployResponse:
    return await run_in_threadpool(_rollout_built_service_sync, service_id, current_user)


def _rollback_service_sync(service_id: UUID, current_user: User) -> RollbackResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to rollback this service")

        previous_image = service.config.get("previous_image")
        if not previous_image:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No previous image is available for rollback")

        deploy = Deploy(
            service_id=service.id,
            status="queued",
            source_type="rollback",
            source_ref=service.image,
            image_tag=previous_image,
        )
        service.status = "rollback_queued"
        session.add(deploy)
        session.add(service)
        session.commit()
        session.refresh(deploy)

        enqueue_rollout_job(deploy.id, service.id, previous_image)
        return RollbackResponse(deploy_id=deploy.id, status=deploy.status, image_tag=previous_image)


@router.post("/{service_id}/rollback", response_model=RollbackResponse, status_code=status.HTTP_202_ACCEPTED)
async def rollback_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> RollbackResponse:
    return await run_in_threadpool(_rollback_service_sync, service_id, current_user)


def _delete_service_sync(service_id: UUID, force: bool, volumes: bool, current_user: User) -> ServiceActionResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to delete this service")

        container = get_service_container_by_slug(service.slug)
        container_id = container.id if container is not None else None
        if container is not None:
            remove_container(container.id, force=force, volumes=volumes)

        for env_var in session.exec(select(EnvVar).where(EnvVar.service_id == service.id)).all():
            session.delete(env_var)
        for secret in session.exec(select(Secret).where(Secret.service_id == service.id)).all():
            session.delete(secret)
        for deploy in session.exec(select(Deploy).where(Deploy.service_id == service.id)).all():
            session.delete(deploy)

        _record_audit_log(
            session,
            current_user,
            "service.delete",
            service,
            {"container_id": container_id, "force": force, "volumes": volumes},
        )
        session.delete(service)
        session.commit()
        return ServiceActionResponse(
            service_id=service_id,
            status="deleted",
            container_id=container_id,
            action="delete",
        )


@router.delete("/{service_id}", response_model=ServiceActionResponse)
async def delete_service(
    service_id: UUID,
    force: bool = True,
    volumes: bool = False,
    current_user: User = Depends(get_current_user),
) -> ServiceActionResponse:
    return await run_in_threadpool(_delete_service_sync, service_id, force, volumes, current_user)


def _list_service_deploys_sync(service_id: UUID, current_user: User) -> list[DeployResponse]:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to view this service")

        deploys = session.exec(
            select(Deploy).where(Deploy.service_id == service_id).order_by(Deploy.created_at.desc())
        ).all()
        return [DeployResponse.from_model(deploy) for deploy in deploys]


@router.get("/{service_id}/deploys", response_model=list[DeployResponse])
async def list_service_deploys(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> list[DeployResponse]:
    return await run_in_threadpool(_list_service_deploys_sync, service_id, current_user)


def _read_deploy_logs_sync(deploy_id: UUID, current_user: User) -> DeployLogsResponse:
    with session_scope() as session:
        deploy = session.get(Deploy, deploy_id)
        if deploy is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deploy not found")

        service = _get_service_or_404(session, deploy.service_id)
        _ensure_service_access(service, current_user, "Not allowed to view deploy logs")

        return DeployLogsResponse(deploy_id=deploy_id, lines=get_deploy_logs(deploy_id))


def _read_service_metrics_sync(
    service_id: UUID,
    current_user: User,
    range_value: str,
) -> list[ServiceMetricSample]:
    parse_metrics_range(range_value)
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to view this service")

    return [ServiceMetricSample(**sample) for sample in metrics_sampler.get_history(service_id, range_value)]


def _list_service_env_sync(service_id: UUID, current_user: User) -> list[ServiceEnvEntry]:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to view this service")
        return [ServiceEnvEntry(**entry) for entry in list_service_env_entries(session, service)]


def _create_service_env_sync(
    service_id: UUID, payload: ServiceEnvUpsertRequest, current_user: User
) -> ServiceEnvMutationResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to update this service")

        entry = upsert_service_env_entry(
            session,
            service,
            payload.key,
            payload.value,
            is_secret=payload.is_secret,
        )
        _record_audit_log(
            session,
            current_user,
            "service.env.upsert",
            service,
            {"key": payload.key, "is_secret": payload.is_secret},
        )

        deploy: Deploy | None = None
        if payload.apply:
            deploy = _queue_env_apply(session, service, current_user, payload.key)
        deploy_id = deploy.id if deploy is not None else None
        image_tag = service.image
        service_status = service.status

        session.commit()
        if deploy_id is not None:
            enqueue_rollout_job(deploy_id, service.id, image_tag)

        return ServiceEnvMutationResponse(
            entry=ServiceEnvEntry(**entry),
            applied=payload.apply,
            deploy_id=deploy_id,
            service_status=service_status,
        )


def _update_service_env_sync(
    service_id: UUID, key: str, payload: ServiceEnvUpdateRequest, current_user: User
) -> ServiceEnvMutationResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to update this service")

        if not service_env_entry_exists(session, service, key):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment variable not found")

        is_secret = payload.is_secret
        if is_secret is None:
            is_secret = session.exec(
                select(Secret).where(Secret.service_id == service.id, Secret.key == key)
            ).first() is not None

        entry = upsert_service_env_entry(
            session,
            service,
            key,
            payload.value,
            is_secret=is_secret,
        )
        _record_audit_log(
            session,
            current_user,
            "service.env.update",
            service,
            {"key": key, "is_secret": is_secret},
        )

        deploy: Deploy | None = None
        if payload.apply:
            deploy = _queue_env_apply(session, service, current_user, key)
        deploy_id = deploy.id if deploy is not None else None
        image_tag = service.image
        service_status = service.status

        session.commit()
        if deploy_id is not None:
            enqueue_rollout_job(deploy_id, service.id, image_tag)

        return ServiceEnvMutationResponse(
            entry=ServiceEnvEntry(**entry),
            applied=payload.apply,
            deploy_id=deploy_id,
            service_status=service_status,
        )


def _delete_service_env_sync(
    service_id: UUID, key: str, apply: bool, current_user: User
) -> ServiceEnvDeleteResponse:
    with session_scope() as session:
        service = _get_service_or_404(session, service_id)
        _ensure_service_access(service, current_user, "Not allowed to update this service")

        deleted = delete_service_env_entry(session, service, key)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment variable not found")

        _record_audit_log(
            session,
            current_user,
            "service.env.delete",
            service,
            {"key": key},
        )

        deploy: Deploy | None = None
        if apply:
            deploy = _queue_env_apply(session, service, current_user, key)
        deploy_id = deploy.id if deploy is not None else None
        image_tag = service.image
        service_status = service.status

        session.commit()
        if deploy_id is not None:
            enqueue_rollout_job(deploy_id, service.id, image_tag)

        return ServiceEnvDeleteResponse(
            key=key,
            deleted=True,
            applied=apply,
            deploy_id=deploy_id,
            service_status=service_status,
        )


@router.get("/deploys/{deploy_id}/logs", response_model=DeployLogsResponse)
async def read_deploy_logs(
    deploy_id: UUID,
    current_user: User = Depends(get_current_user),
) -> DeployLogsResponse:
    return await run_in_threadpool(_read_deploy_logs_sync, deploy_id, current_user)


@router.get("/{service_id}/metrics", response_model=list[ServiceMetricSample])
async def read_service_metrics(
    service_id: UUID,
    range: str = "5m",
    current_user: User = Depends(get_current_user),
) -> list[ServiceMetricSample]:
    try:
        return await run_in_threadpool(_read_service_metrics_sync, service_id, current_user, range)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{service_id}/env", response_model=list[ServiceEnvEntry])
async def list_service_env(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
) -> list[ServiceEnvEntry]:
    return await run_in_threadpool(_list_service_env_sync, service_id, current_user)


@router.post("/{service_id}/env", response_model=ServiceEnvMutationResponse, status_code=status.HTTP_201_CREATED)
async def create_service_env(
    service_id: UUID,
    payload: ServiceEnvUpsertRequest,
    current_user: User = Depends(get_current_user),
) -> ServiceEnvMutationResponse:
    return await run_in_threadpool(_create_service_env_sync, service_id, payload, current_user)


@router.put("/{service_id}/env/{key}", response_model=ServiceEnvMutationResponse)
async def update_service_env(
    service_id: UUID,
    key: str,
    payload: ServiceEnvUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> ServiceEnvMutationResponse:
    return await run_in_threadpool(_update_service_env_sync, service_id, key, payload, current_user)


@router.delete("/{service_id}/env/{key}", response_model=ServiceEnvDeleteResponse)
async def delete_service_env(
    service_id: UUID,
    key: str,
    apply: bool = True,
    current_user: User = Depends(get_current_user),
) -> ServiceEnvDeleteResponse:
    return await run_in_threadpool(_delete_service_env_sync, service_id, key, apply, current_user)
