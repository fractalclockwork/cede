"""Build step: run the Toolchain Image to compile firmware (DS-7, DS-6.3)."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

from cede.identity import generate_build_identity, write_digest_sidecar
from cede.target_type import TargetType


def run_build(
    *,
    target_type: TargetType,
    app_dir: Path,
    workspace: Path,
    digest: str | None = None,
) -> Path:
    """Build firmware using the toolchain container.

    Args:
        target_type: Loaded TargetType manifest.
        app_dir: Application directory (relative to workspace or absolute).
        workspace: Repository root (mounted into container).
        digest: Build Identity token. Generated from git if not provided.

    Returns:
        Path to the built artifact.

    Raises:
        SystemExit: If the build fails or no artifact is produced.
    """
    build_identity = digest or generate_build_identity(workspace)

    app_rel = app_dir.relative_to(workspace) if app_dir.is_absolute() else app_dir

    build_command = target_type.toolchain.build_command.format(
        sketch_dir=f"/workspace/{app_rel}",
        app_dir=f"/workspace/{app_rel}",
        workspace="/workspace",
        digest=build_identity,
    )

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{workspace}:/workspace",
        "-w", f"/workspace/{app_rel}",
        "-e", f"CEDE_IMAGE_ID={build_identity}",
        target_type.toolchain.image,
        "sh", "-c", build_command,
    ]

    print(f"[cede build] target={target_type.target_type} digest={build_identity}", file=sys.stderr)
    print(f"[cede build] docker run {target_type.toolchain.image}", file=sys.stderr)

    result = subprocess.run(cmd, cwd=workspace)
    if result.returncode != 0:
        print(f"[cede build] FAILED (exit {result.returncode})", file=sys.stderr)
        raise SystemExit(1)

    if hasattr(os, "getuid"):
        # Docker created build files as root; reclaim them for the host user
        # so subsequent writes (digest sidecar) succeed.
        build_dir = app_dir / "build"
        if build_dir.exists():
            subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{workspace}:/workspace",
                    "-w", "/workspace",
                    "alpine",
                    "chown", "-R", f"{os.getuid()}:{os.getgid()}",
                    str(build_dir.relative_to(workspace) if build_dir.is_absolute() else build_dir),
                ],
                check=False,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )

    artifact = _find_artifact(app_dir, target_type.toolchain.artifact_pattern)
    if artifact is None:
        print(
            f"[cede build] ERROR: no artifact matching '{target_type.toolchain.artifact_pattern}' in {app_dir}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    sidecar = write_digest_sidecar(artifact, build_identity)
    print(f"[cede build] artifact: {artifact}", file=sys.stderr)
    print(f"[cede build] sidecar:  {sidecar}", file=sys.stderr)

    return artifact


def _find_artifact(app_dir: Path, pattern: str) -> Path | None:
    """Find the first file matching artifact_pattern in app_dir."""
    matches = sorted(glob.glob(str(app_dir / pattern)))
    if matches:
        return Path(matches[0])
    return None
