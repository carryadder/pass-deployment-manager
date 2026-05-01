from pathlib import Path

from backend.app.core.builder import cleanup_repository


def test_cleanup_repository_removes_directory(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "Dockerfile").write_text("FROM busybox\n", encoding="utf-8")

    cleanup_repository(repo_dir)

    assert repo_dir.exists() is False
