"""Composite commands that chain build, deploy, and validate (DS-7.1)."""

from __future__ import annotations

import sys
from pathlib import Path

from cede.build import run_build
from cede.deploy import run_deploy
from cede.identity import generate_build_identity, read_digest_sidecar
from cede.target_type import TargetType
from cede.transport import Transport
from cede.validate import run_validate


def run_flash_test(
    *,
    target_type: TargetType,
    artifact: Path,
    transport: Transport,
    digest: str | None = None,
    port: str | None = None,
    banner_prefix: str | None = None,
) -> None:
    """Deploy firmware and immediately validate it.

    Equivalent to: cede deploy + cede validate.
    """
    if not artifact.exists():
        print(f"[cede flash-test] ERROR: artifact not found: {artifact}", file=sys.stderr)
        raise SystemExit(1)

    resolved_digest = digest or read_digest_sidecar(artifact) or "unknown"

    print(f"[cede flash-test] deploy + validate target={target_type.target_type}", file=sys.stderr)

    run_deploy(target_type=target_type, artifact=artifact, transport=transport, port=port)
    run_validate(
        target_type=target_type,
        digest=resolved_digest,
        transport=transport,
        port=port,
        banner_prefix=banner_prefix,
    )


def run_full(
    *,
    target_type: TargetType,
    app_dir: Path,
    workspace: Path,
    transport: Transport,
    digest: str | None = None,
    port: str | None = None,
    banner_prefix: str | None = None,
) -> None:
    """Build, deploy, and validate in one shot.

    Equivalent to: cede build + cede deploy + cede validate.
    """
    print(f"[cede run] build + deploy + validate target={target_type.target_type}", file=sys.stderr)

    artifact = run_build(
        target_type=target_type,
        app_dir=app_dir,
        workspace=workspace,
        digest=digest,
    )

    build_digest = digest or read_digest_sidecar(artifact) or generate_build_identity(workspace)

    run_deploy(target_type=target_type, artifact=artifact, transport=transport, port=port)
    run_validate(
        target_type=target_type,
        digest=build_digest,
        transport=transport,
        port=port,
        banner_prefix=banner_prefix,
    )
