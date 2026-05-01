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
from backend.app.models.deploy import Deploy
from backend.app.models.service import Service

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
