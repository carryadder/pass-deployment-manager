from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from docker.errors import BuildError, DockerException
from sqlmodel import Session

from backend.app.db import engine
from backend.app.core.builder import (
    RepositoryCloneError,
    build_image_from_repo,
    cleanup_repository,
    clone_repository,
)
from backend.app.core.runner import (
    get_container_by_name,
    get_service_container_by_slug,
    remove_service_container_by_name,
    run_service,
    stop_and_remove_container,
    wait_for_container_ready,
)
from backend.app.core.service_env import build_service_environment
from backend.app.models.deploy import Deploy
from backend.app.models.project import Project
from backend.app.models.service import Service
from backend.app.core.traefik import TraefikConfigError, build_service_routing

executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="deploy-worker")
deploy_logs: dict[str, list[str]] = {}


def _append_log(deploy_id: UUID, message: str) -> None:
    deploy_logs.setdefault(str(deploy_id), []).append(message)


def _short_ref(value: str | None) -> str:
    if not value:
        return "latest"
    return value[:7]


def enqueue_deploy_job(
    deploy_id: UUID,
    service_id: UUID,
    git_url: str,
    branch: str | None,
    commit: str | None,
    build_context_path: str | None,
    dockerfile_path: str | None,
    build_args: dict[str, str],
) -> None:
    executor.submit(
        _run_deploy_job,
        deploy_id,
        service_id,
        git_url,
        branch,
        commit,
        build_context_path,
        dockerfile_path,
        build_args,
    )


def get_deploy_logs(deploy_id: UUID) -> list[str]:
    return deploy_logs.get(str(deploy_id), [])


def _run_deploy_job(
    deploy_id: UUID,
    service_id: UUID,
    git_url: str,
    branch: str | None,
    commit: str | None,
    build_context_path: str | None,
    dockerfile_path: str | None,
    build_args: dict[str, str],
) -> None:
    repo_path: Path | None = None

    with Session(engine) as session:
        deploy = session.get(Deploy, deploy_id)
        service = session.get(Service, service_id)
        if deploy is None or service is None:
            return
        deploy.status = "building"
        session.add(deploy)
        session.commit()

    try:
        _append_log(deploy_id, f"Cloning repository: {git_url}")
        repo_path = clone_repository(git_url=git_url, branch=branch, commit=commit)
        image_tag = f"dmgr/{service.slug}:{_short_ref(commit or branch)}"
        _append_log(deploy_id, f"Building image: {image_tag}")
        _, build_output = build_image_from_repo(
            repo_path=repo_path,
            image_tag=image_tag,
            build_context_path=build_context_path,
            dockerfile_path=dockerfile_path,
            build_args=build_args,
        )
        for line in build_output:
            _append_log(deploy_id, line)

        with Session(engine) as session:
            deploy = session.get(Deploy, deploy_id)
            service = session.get(Service, service_id)
            if deploy is None or service is None:
                return
            deploy.status = "built"
            deploy.image_tag = image_tag
            service.image = image_tag
            service.status = "built"
            session.add(deploy)
            session.add(service)
            session.commit()
    except (RepositoryCloneError, BuildError, DockerException) as exc:
        _append_log(deploy_id, f"[deploy-error] {exc}")
        with Session(engine) as session:
            deploy = session.get(Deploy, deploy_id)
            service = session.get(Service, service_id)
            if deploy is not None:
                deploy.status = "failed"
                session.add(deploy)
            if service is not None:
                service.status = "build_failed"
                session.add(service)
            session.commit()
    finally:
        if repo_path is not None:
            cleanup_repository(repo_path)


def enqueue_rollout_job(deploy_id: UUID, service_id: UUID, image_tag: str) -> None:
    executor.submit(_run_rollout_job, deploy_id, service_id, image_tag)


def _run_rollout_job(deploy_id: UUID, service_id: UUID, image_tag: str) -> None:
    with Session(engine) as session:
        deploy = session.get(Deploy, deploy_id)
        service = session.get(Service, service_id)
        project = session.get(Project, service.project_id) if service is not None else None
        if deploy is None or service is None:
            return
        deploy.status = "rolling_out"
        service.status = "rolling_out"
        session.add(deploy)
        session.add(service)
        session.commit()
        service_slug = service.slug
        service_name = service.name
        service_config = dict(service.config)
        current_image = service.image
        project_id = str(project.id) if project is not None else str(service.project_id)
        owner_id = str(project.owner_id) if project is not None else None
        runtime_env = build_service_environment(session, service)

    previous_container = get_service_container_by_slug(service_slug)
    has_host_port_conflict = any(
        port.get("host_port") is not None for port in service_config.get("ports", [])
    )
    if previous_container is not None and has_host_port_conflict:
        _append_log(deploy_id, "Published ports detected; stopping current container before rollout.")
        stop_and_remove_container(previous_container)
        previous_container = None

    candidate_name = f"{service_slug}-candidate-{str(deploy_id)[:8]}"
    base_labels = {
        "dmgr.service.slug": service_slug,
        "dmgr.project.id": project_id,
    }
    if owner_id is not None:
        base_labels["dmgr.owner.id"] = owner_id

    try:
        routing = build_service_routing(
            service_slug=service_slug,
            domain=service_config.get("domain"),
            ports=service_config.get("ports", []),
            requested_network=service_config.get("network"),
            base_labels=base_labels,
        )
    except TraefikConfigError as exc:
        _append_log(deploy_id, f"[rollout-error] {exc}")
        with Session(engine) as session:
            deploy = session.get(Deploy, deploy_id)
            service = session.get(Service, service_id)
            if deploy is not None:
                deploy.status = "failed"
                session.add(deploy)
            if service is not None:
                service.status = "rollout_failed"
                session.add(service)
            session.commit()
        return

    rollout_payload = {
        **service_config,
        "name": candidate_name,
        "image": image_tag,
        "env": runtime_env,
        "labels": routing["labels"],
        "network": routing["network"],
        "extra_networks": routing["extra_networks"],
    }

    try:
        _append_log(deploy_id, f"Starting candidate container from {image_tag}")
        run_service(rollout_payload)
        candidate = get_container_by_name(candidate_name)
        if candidate is None:
            raise DockerException("Candidate container could not be located after startup")
        wait_for_container_ready(candidate)
        _append_log(deploy_id, "Candidate container passed readiness checks")

        if previous_container is not None:
            _append_log(deploy_id, "Stopping previous container")
            stop_and_remove_container(previous_container)

        try:
            candidate.rename(service_slug)
            candidate.reload()
        except Exception:
            candidate.reload()

        with Session(engine) as session:
            deploy = session.get(Deploy, deploy_id)
            service = session.get(Service, service_id)
            if deploy is None or service is None:
                return
            config = dict(service.config)
            config["previous_image"] = current_image
            config["current_container_name"] = candidate.name
            config["current_container_id"] = candidate.id
            config["last_successful_deploy_id"] = str(deploy.id)
            service.config = config
            service.name = service_name
            service.image = image_tag
            service.status = "running"
            deploy.status = "running"
            deploy.image_tag = image_tag
            session.add(service)
            session.add(deploy)
            session.commit()
    except DockerException as exc:
        _append_log(deploy_id, f"[rollout-error] {exc}")
        remove_service_container_by_name(candidate_name)
        with Session(engine) as session:
            deploy = session.get(Deploy, deploy_id)
            service = session.get(Service, service_id)
            if deploy is not None:
                deploy.status = "failed"
                session.add(deploy)
            if service is not None:
                service.status = "rollout_failed"
                session.add(service)
            session.commit()
