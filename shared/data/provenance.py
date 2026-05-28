from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
import subprocess
from typing import Any


def input_data_metadata(
    paths: Sequence[str | Path],
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    sha256: dict[str, str] = {}
    byte_counts: dict[str, int] = {}
    is_repo_relative = True
    non_reproducible_paths: list[str] = []

    for path_value in paths:
        path = Path(path_value).resolve()
        key = repo_key(path, repo_root=root)
        repo_relative = not Path(key).is_absolute()
        is_repo_relative = is_repo_relative and repo_relative
        if not repo_relative:
            non_reproducible_paths.append(key)
        sha256[key] = _sha256(path)
        byte_counts[key] = path.stat().st_size

    return {
        "sha256": sha256,
        "bytes": byte_counts,
        "is_repo_relative": is_repo_relative,
        "non_reproducible_paths": non_reproducible_paths,
    }


def repo_key(path: str | Path, *, repo_root: str | Path) -> str:
    root = Path(repo_root).resolve()
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def code_version(repo_root: str | Path) -> str:
    root = Path(repo_root).resolve()
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"

    version = commit.stdout.strip()
    if status.stdout.strip():
        version = f"{version}-dirty"
    return version


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
