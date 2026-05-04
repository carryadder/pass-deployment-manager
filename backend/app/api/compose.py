from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import User, get_current_user
from backend.app.api.services import (
    HealthcheckConfig,
    PortMapping,
    ServiceCreateRequest,
    VolumeMapping,
    _create_service_sync,
)
from backend.app.core.compose import (
    ComposeParseError,
    ParsedService,
    parse_compose,
)
from backend.app.core.builder import (
    RepositoryCloneError,
    cleanup_repository,
    clone_repository,
)

router = APIRouter(prefix="/api/compose", tags=["compose"])


class ComposePreviewRequest(BaseModel):
    yaml: str = Field(min_length=1, max_length=200_000)
    name_prefix: str = Field(default="", max_length=64)


class ComposePreviewService(BaseModel):
    name: str
    image: str
    cpus: float
    memory_mb: int
    env_keys: list[str] = Field(default_factory=list)
    port_count: int
    volume_count: int
    network: str | None = None
    restart_policy: str
    healthcheck: bool
    warnings: list[str] = Field(default_factory=list)


class ComposePreviewResponse(BaseModel):
    services: list[ComposePreviewService]
    declared_volumes: list[str]
    declared_networks: list[str]
    document_warnings: list[str] = Field(default_factory=list)
    compose_path: str | None = None


class ComposeImportRequest(BaseModel):
    yaml: str = Field(min_length=1, max_length=200_000)
    name_prefix: str = Field(default="", max_length=64)
    only: list[str] = Field(default_factory=list)


class ComposeImportedService(BaseModel):
    compose_name: str
    service_name: str
    service_id: UUID
    deploy_id: UUID
    image: str
    status: str


class ComposeImportSkipped(BaseModel):
    compose_name: str
    reason: str


class ComposeImportResponse(BaseModel):
    imported: list[ComposeImportedService] = Field(default_factory=list)
    skipped: list[ComposeImportSkipped] = Field(default_factory=list)
    document_warnings: list[str] = Field(default_factory=list)
    compose_path: str | None = None


class ComposeRepoPreviewRequest(BaseModel):
    git_url: str = Field(min_length=1, max_length=1000)
    branch: str | None = Field(default=None, max_length=255)
    commit: str | None = Field(default=None, max_length=255)
    compose_path: str | None = Field(default=None, max_length=1000)
    name_prefix: str = Field(default="", max_length=64)


class ComposeRepoImportRequest(BaseModel):
    git_url: str = Field(min_length=1, max_length=1000)
    branch: str | None = Field(default=None, max_length=255)
    commit: str | None = Field(default=None, max_length=255)
    compose_path: str | None = Field(default=None, max_length=1000)
    name_prefix: str = Field(default="", max_length=64)
    only: list[str] = Field(default_factory=list)


_DEFAULT_COMPOSE_FILENAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)


def _service_name_from_compose(prefix: str, compose_name: str) -> str:
    prefix = prefix.strip()
    if prefix:
        return f"{prefix}-{compose_name}"
    return compose_name


def _resolve_compose_file(repo_path: Path, compose_path: str | None) -> Path:
    if compose_path and compose_path.strip():
        candidate = (repo_path / compose_path.strip()).resolve()
        try:
            candidate.relative_to(repo_path.resolve())
        except ValueError as exc:
            raise ComposeParseError("Compose path must stay inside the cloned repository.") from exc
        if not candidate.is_file():
            raise ComposeParseError(f"Compose file not found at '{compose_path.strip()}'.")
        return candidate

    root_matches = [repo_path / name for name in _DEFAULT_COMPOSE_FILENAMES if (repo_path / name).is_file()]
    if len(root_matches) == 1:
        return root_matches[0]
    if len(root_matches) > 1:
        choices = ", ".join(path.name for path in root_matches)
        raise ComposeParseError(
            f"Multiple compose files were found at the repo root ({choices}); specify compose_path."
        )

    matches = sorted(
        path
        for name in _DEFAULT_COMPOSE_FILENAMES
        for path in repo_path.rglob(name)
        if path.is_file()
    )
    if not matches:
        raise ComposeParseError("No docker compose file was found in the repository.")
    if len(matches) > 1:
        choices = ", ".join(str(path.relative_to(repo_path)) for path in matches[:5])
        suffix = "" if len(matches) <= 5 else ", ..."
        raise ComposeParseError(
            f"Multiple compose files were found ({choices}{suffix}); specify compose_path."
        )
    return matches[0]


def _load_compose_yaml_from_repo(
    git_url: str,
    branch: str | None,
    commit: str | None,
    compose_path: str | None,
) -> tuple[str, str]:
    repo_path: Path | None = None
    try:
        repo_path = clone_repository(git_url=git_url, branch=branch, commit=commit)
        compose_file = _resolve_compose_file(repo_path, compose_path)
        return compose_file.read_text(encoding="utf-8"), str(compose_file.relative_to(repo_path))
    except RepositoryCloneError as exc:
        raise ComposeParseError(f"Unable to clone repository: {exc}") from exc
    except OSError as exc:
        raise ComposeParseError(f"Unable to read compose file: {exc}") from exc
    finally:
        if repo_path is not None:
            cleanup_repository(repo_path)


def _to_create_request(parsed: ParsedService, name_prefix: str) -> ServiceCreateRequest:
    healthcheck = (
        HealthcheckConfig(
            type=parsed.healthcheck.type,
            value=parsed.healthcheck.value,
            interval_seconds=parsed.healthcheck.interval_seconds,
            timeout_seconds=parsed.healthcheck.timeout_seconds,
            start_period_seconds=parsed.healthcheck.start_period_seconds,
            retries=parsed.healthcheck.retries,
        )
        if parsed.healthcheck is not None
        else None
    )
    return ServiceCreateRequest(
        name=_service_name_from_compose(name_prefix, parsed.name),
        image=parsed.image,
        cpus=parsed.cpus,
        memory_mb=parsed.memory_mb,
        env=parsed.env,
        ports=[PortMapping(container_port=p.container_port, host_port=p.host_port) for p in parsed.ports],
        volumes=[VolumeMapping(source=v.source, target=v.target, mode=v.mode) for v in parsed.volumes],
        network=parsed.network,
        domain=None,
        healthcheck=healthcheck,
        restart_policy=parsed.restart_policy,
        pids_limit=parsed.pids_limit,
    )


def _preview_sync(payload: ComposePreviewRequest) -> ComposePreviewResponse:
    parsed = parse_compose(payload.yaml)
    services = [
        ComposePreviewService(
            name=_service_name_from_compose(payload.name_prefix, service.name),
            image=service.image,
            cpus=service.cpus,
            memory_mb=service.memory_mb,
            env_keys=sorted(service.env.keys()),
            port_count=len(service.ports),
            volume_count=len(service.volumes),
            network=service.network,
            restart_policy=service.restart_policy,
            healthcheck=service.healthcheck is not None,
            warnings=service.warnings,
        )
        for service in parsed.services
    ]
    return ComposePreviewResponse(
        services=services,
        declared_volumes=parsed.declared_volumes,
        declared_networks=parsed.declared_networks,
        document_warnings=parsed.warnings,
    )


def _preview_repo_sync(payload: ComposeRepoPreviewRequest) -> ComposePreviewResponse:
    yaml_text, resolved_compose_path = _load_compose_yaml_from_repo(
        git_url=payload.git_url,
        branch=payload.branch,
        commit=payload.commit,
        compose_path=payload.compose_path,
    )
    response = _preview_sync(
        ComposePreviewRequest(
            yaml=yaml_text,
            name_prefix=payload.name_prefix,
        )
    )
    response.compose_path = resolved_compose_path
    return response


def _import_sync(payload: ComposeImportRequest, current_user: User) -> ComposeImportResponse:
    parsed = parse_compose(payload.yaml)

    selected: set[str] = set(payload.only or [])
    imported: list[ComposeImportedService] = []
    skipped: list[ComposeImportSkipped] = []

    for service in parsed.services:
        if selected and service.name not in selected:
            skipped.append(
                ComposeImportSkipped(
                    compose_name=service.name,
                    reason="Not in the requested 'only' list.",
                )
            )
            continue
        try:
            create_request = _to_create_request(service, payload.name_prefix)
        except Exception as exc:  # pydantic validation errors etc.
            skipped.append(
                ComposeImportSkipped(compose_name=service.name, reason=f"Invalid service: {exc}")
            )
            continue
        try:
            response = _create_service_sync(create_request, current_user)
        except HTTPException as exc:
            skipped.append(
                ComposeImportSkipped(compose_name=service.name, reason=f"{exc.detail}")
            )
            continue

        imported.append(
            ComposeImportedService(
                compose_name=service.name,
                service_name=create_request.name,
                service_id=response.service_id,
                deploy_id=response.deploy_id,
                image=response.image,
                status=response.status,
            )
        )

    return ComposeImportResponse(
        imported=imported,
        skipped=skipped,
        document_warnings=parsed.warnings,
    )


def _import_repo_sync(payload: ComposeRepoImportRequest, current_user: User) -> ComposeImportResponse:
    yaml_text, resolved_compose_path = _load_compose_yaml_from_repo(
        git_url=payload.git_url,
        branch=payload.branch,
        commit=payload.commit,
        compose_path=payload.compose_path,
    )
    response = _import_sync(
        ComposeImportRequest(
            yaml=yaml_text,
            name_prefix=payload.name_prefix,
            only=payload.only,
        ),
        current_user,
    )
    response.compose_path = resolved_compose_path
    return response


@router.post("/preview", response_model=ComposePreviewResponse)
async def preview_compose(payload: ComposePreviewRequest) -> ComposePreviewResponse:
    try:
        return await run_in_threadpool(_preview_sync, payload)
    except ComposeParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/preview-repo", response_model=ComposePreviewResponse)
async def preview_compose_repo(payload: ComposeRepoPreviewRequest) -> ComposePreviewResponse:
    try:
        return await run_in_threadpool(_preview_repo_sync, payload)
    except ComposeParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/import", response_model=ComposeImportResponse, status_code=status.HTTP_201_CREATED)
async def import_compose(
    payload: ComposeImportRequest,
    current_user: User = Depends(get_current_user),
) -> ComposeImportResponse:
    try:
        return await run_in_threadpool(_import_sync, payload, current_user)
    except ComposeParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/import-repo", response_model=ComposeImportResponse, status_code=status.HTTP_201_CREATED)
async def import_compose_repo(
    payload: ComposeRepoImportRequest,
    current_user: User = Depends(get_current_user),
) -> ComposeImportResponse:
    try:
        return await run_in_threadpool(_import_repo_sync, payload, current_user)
    except ComposeParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
