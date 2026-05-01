from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.auth import User, get_current_user
from backend.app.db import get_session
from backend.app.models.deploy import Deploy
from backend.app.models.project import Project
from backend.app.models.service import Service
from backend.app.core.runner import DockerException, run_service
from backend.app.workers.tasks import enqueue_deploy_job, enqueue_rollout_job, get_deploy_logs

router = APIRouter(prefix="/api/services", tags=["services"])


class PortMapping(BaseModel):
    container_port: int = Field(gt=0, le=65535)
    host_port: int | None = Field(default=None, gt=0, le=65535)


class VolumeMapping(BaseModel):
    source: str = Field(min_length=1, max_length=255)
    target: str = Field(min_length=1, max_length=255)
    mode: str = Field(default="rw", pattern="^(ro|rw)$")


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


def _slugify(name: str) -> str:
    slug = "-".join(name.lower().strip().split())
    return "".join(ch for ch in slug if ch.isalnum() or ch == "-").strip("-") or "service"


def _ensure_default_project(session: Session, user: User) -> Project:
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


def _get_service_or_404(session: Session, service_id: UUID) -> Service:
    service = session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.post("", response_model=ServiceCreateResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ServiceCreateResponse:
    project = _ensure_default_project(session, current_user)
    service_slug = f"{_slugify(payload.name)}-{str(current_user.id)[:8]}"
    service_config = payload.model_dump()
    runner_payload = {
        **service_config,
        "name": service_slug,
        "labels": {
            "dmgr.service.slug": service_slug,
            "dmgr.project.id": str(project.id),
            "dmgr.owner.id": str(current_user.id),
        },
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
            **service_config,
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


@router.post("/{service_id}/deploy", response_model=DeployResponse, status_code=status.HTTP_202_ACCEPTED)
def deploy_service_from_git(
    service_id: UUID,
    payload: ServiceDeployRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DeployResponse:
    service = _get_service_or_404(session, service_id)
    if service.project is not None and service.project.owner_id != current_user.id and not current_user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to deploy this service")

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


@router.post("/{service_id}/rollout", response_model=DeployResponse, status_code=status.HTTP_202_ACCEPTED)
def rollout_built_service(
    service_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DeployResponse:
    service = _get_service_or_404(session, service_id)
    if service.project is not None and service.project.owner_id != current_user.id and not current_user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to deploy this service")

    deploy = session.exec(
        select(Deploy).where(Deploy.service_id == service_id).order_by(Deploy.created_at.desc())
    ).first()
    if deploy is None or deploy.image_tag is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No built deploy is available for rollout")
    if deploy.status not in {"built", "rollout_failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Latest deploy is not ready for rollout")

    enqueue_rollout_job(deploy.id, service.id, deploy.image_tag)
    return DeployResponse.from_model(deploy)


@router.post("/{service_id}/rollback", response_model=RollbackResponse, status_code=status.HTTP_202_ACCEPTED)
def rollback_service(
    service_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RollbackResponse:
    service = _get_service_or_404(session, service_id)
    if service.project is not None and service.project.owner_id != current_user.id and not current_user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to rollback this service")

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


@router.get("/{service_id}/deploys", response_model=list[DeployResponse])
def list_service_deploys(
    service_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[DeployResponse]:
    service = _get_service_or_404(session, service_id)
    if service.project is not None and service.project.owner_id != current_user.id and not current_user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this service")

    deploys = session.exec(
        select(Deploy).where(Deploy.service_id == service_id).order_by(Deploy.created_at.desc())
    ).all()
    return [DeployResponse.from_model(deploy) for deploy in deploys]


@router.get("/deploys/{deploy_id}/logs", response_model=DeployLogsResponse)
def read_deploy_logs(
    deploy_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DeployLogsResponse:
    deploy = session.get(Deploy, deploy_id)
    if deploy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deploy not found")

    service = _get_service_or_404(session, deploy.service_id)
    if service.project is not None and service.project.owner_id != current_user.id and not current_user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view deploy logs")

    return DeployLogsResponse(deploy_id=deploy_id, lines=get_deploy_logs(deploy_id))
