"""Build Identity generation and sidecar management (DS-9)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def generate_build_identity(repo_dir: Path | None = None) -> str:
    """Generate a Build Identity token.

    Uses git short SHA (12 chars) of HEAD. Falls back to 'nogit' if
    not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_dir,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"


def write_digest_sidecar(artifact_path: Path, digest: str) -> Path:
    """Write a .digest sidecar file alongside an artifact.

    Returns the path to the sidecar file.
    """
    sidecar = artifact_path.with_suffix(artifact_path.suffix + ".digest")
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return sidecar


def read_digest_sidecar(artifact_path: Path) -> str | None:
    """Read the .digest sidecar for an artifact, if it exists."""
    sidecar = artifact_path.with_suffix(artifact_path.suffix + ".digest")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").strip()
    return None
