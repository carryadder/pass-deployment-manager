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
        config=service_config,
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
