"""Deploy step: transfer artifact and flash the target (DS-7, DS-8)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from cede.target_type import TargetType
from cede.transport import Transport


def run_deploy(
    *,
    target_type: TargetType,
    artifact: Path,
    transport: Transport,
    port: str | None = None,
) -> None:
    """Deploy an artifact to a target.

    1. Copy the artifact to the target's host (gateway or local).
    2. Run pre_flash if defined.
    3. Run the flash command.
    4. Wait post_flash_delay_s.

    Args:
        target_type: Target Type manifest.
        artifact: Path to the built firmware binary.
        transport: Transport instance (Direct or SSH).
        port: Serial port override (for flash commands needing {port}).

    Raises:
        SystemExit: If flashing fails.
    """
    if not artifact.exists():
        print(f"[cede deploy] ERROR: artifact not found: {artifact}", file=sys.stderr)
        raise SystemExit(1)

    remote_artifact = f"/tmp/{artifact.name}"

    print(f"[cede deploy] target={target_type.target_type} artifact={artifact.name}", file=sys.stderr)

    transport.copy_file(artifact, remote_artifact)

    if target_type.flash.pre_flash:
        print(f"[cede deploy] pre-flash: {target_type.flash.pre_flash}", file=sys.stderr)
        transport.run_command(
            ["sh", "-c", target_type.flash.pre_flash],
            check=False,
        )

    resolved_port = port
    if not resolved_port and "{port}" in target_type.flash.command:
        resolved_port = _resolve_port(transport, target_type) or ""
    resolved_port = resolved_port or ""

    flash_cmd = target_type.resolve_flash_command(artifact=remote_artifact, port=resolved_port)
    print(f"[cede deploy] flash: {flash_cmd}", file=sys.stderr)

    result = transport.run_command(["sh", "-c", flash_cmd], check=False)
    if result.returncode != 0:
        print(f"[cede deploy] FAILED (exit {result.returncode})", file=sys.stderr)
        raise SystemExit(1)

    if target_type.flash.post_flash_delay_s > 0:
        delay = target_type.flash.post_flash_delay_s
        print(f"[cede deploy] waiting {delay}s for target reboot...", file=sys.stderr)
        time.sleep(delay)

    print("[cede deploy] OK", file=sys.stderr)


def _resolve_port(transport: Transport, target_type: TargetType) -> str | None:
    """Resolve the first matching serial device on the deploy host."""
    dm = target_type.serial.device_match
    globs: list[str] = []
    if dm.by_id_glob:
        globs.append(dm.by_id_glob)
    globs.extend(dm.fallback_globs)
    if not globs:
        return None
    glob_args = " ".join(f"'{g}'" for g in globs)
    cmd = [
        "sh", "-c",
        f"for g in {glob_args}; do for f in $(ls -1 $g 2>/dev/null); do echo $f; exit 0; done; done; exit 1",
    ]
    result = transport.run_command(cmd, check=False, capture_output=True)
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    if result.returncode == 0 and stdout.strip():
        return stdout.strip().splitlines()[0]
    return None
