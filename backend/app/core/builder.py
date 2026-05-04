from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp

from docker.errors import BuildError, DockerException

from backend.app.config import get_settings
from backend.app.core.docker_client import get_docker_client


class RepositoryCloneError(RuntimeError):
    pass


def _run_git_command(args: list[str], workdir: Path | None = None) -> None:
    try:
        subprocess.run(
            args,
            cwd=str(workdir) if workdir else None,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RepositoryCloneError(exc.stderr.strip() or exc.stdout.strip() or str(exc)) from exc


def clone_repository(git_url: str, branch: str | None = None, commit: str | None = None) -> Path:
    settings = get_settings()
    workspace = settings.deploy_workspace
    workspace.mkdir(parents=True, exist_ok=True)

    target_dir = Path(mkdtemp(prefix="build-", dir=workspace))
    clone_args = ["git", "clone", "--depth", "1"]
    if branch:
        clone_args.extend(["--branch", branch])
    clone_args.extend([git_url, str(target_dir)])
    _run_git_command(clone_args)

    if commit:
        _run_git_command(["git", "fetch", "--depth", "1", "origin", commit], workdir=target_dir)
        _run_git_command(["git", "checkout", commit], workdir=target_dir)

    return target_dir


def build_image_from_repo(
    repo_path: Path,
    image_tag: str,
    build_context_path: str | None = None,
    dockerfile_path: str | None = None,
    build_args: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    client = get_docker_client()
    logs: list[str] = []
    build_context = repo_path / build_context_path if build_context_path else repo_path

    try:
        image, build_logs = client.images.build(
            path=str(build_context),
            tag=image_tag,
            dockerfile=dockerfile_path,
            buildargs=build_args or None,
            rm=True,
        )
    except BuildError as exc:
        for entry in exc.build_log:
            message = entry.get("stream") or entry.get("error") or str(entry)
            logs.append(message.rstrip())
        raise
    except DockerException:
        raise

    for entry in build_logs:
        message = entry.get("stream") or entry.get("status") or entry.get("error") or str(entry)
        logs.append(message.rstrip())

    return image.id, [line for line in logs if line]


def cleanup_repository(repo_path: Path) -> None:
    shutil.rmtree(repo_path, ignore_errors=True)
