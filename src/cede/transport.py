"""Transport layer abstraction (DS-8, DS-12).

Provides a common interface for executing commands and transferring files,
with implementations for both Gateway Mode (SSH) and Direct-Attach Mode (local).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class Transport(Protocol):
    """Interface for command execution and file transfer between tiers."""

    def run_command(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output: bool = False,
        cwd: Path | str | None = None,
    ) -> subprocess.CompletedProcess[str]: ...

    def copy_file(self, local_path: Path, remote_path: str) -> None: ...

    def sync_dir(self, local_dir: Path, remote_dir: str) -> None: ...


@dataclass
class DirectTransport:
    """Direct-Attach mode: all commands run locally on the Dev-Host (DS-12.1)."""

    def run_command(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output: bool = False,
        cwd: Path | str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
            cwd=cwd,
        )

    def copy_file(self, local_path: Path, remote_path: str) -> None:
        # In direct mode, "remote" is just another local path
        import shutil
        dest = Path(remote_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)

    def sync_dir(self, local_dir: Path, remote_dir: str) -> None:
        import shutil
        dest = Path(remote_dir)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(local_dir, dest)


@dataclass
class SSHTransport:
    """Gateway mode: commands execute on the gateway over SSH (DS-12.2).

    Attributes:
        ssh_host: Full SSH address (e.g. 'pi@cede-pi.local').
        work_dir: Working directory on the gateway (default: ~/cede).
    """

    ssh_host: str
    work_dir: str = "~/cede"

    @property
    def _ssh_target(self) -> str:
        return self.ssh_host

    def run_command(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output: bool = False,
        cwd: Path | str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        import shlex

        remote_cmd = shlex.join(cmd)
        if cwd:
            remote_cmd = f"cd {shlex.quote(str(cwd))} && {remote_cmd}"

        ssh_cmd = ["ssh", self._ssh_target, remote_cmd]

        return subprocess.run(
            ssh_cmd,
            check=check,
            capture_output=capture_output,
            text=True,
        )

    def copy_file(self, local_path: Path, remote_path: str) -> None:
        dest = f"{self._ssh_target}:{remote_path}"
        subprocess.run(
            ["scp", str(local_path), dest],
            check=True,
        )

    def sync_dir(self, local_dir: Path, remote_dir: str) -> None:
        dest = f"{self._ssh_target}:{remote_dir}/"
        subprocess.run(
            ["rsync", "-az", "--delete", f"{local_dir}/", dest],
            check=True,
        )


def resolve_transport(
    *,
    mode: str | None = None,
    target_attach: str | None = None,
    gateway_host: str | None = None,
    gateway_user: str | None = None,
    gateway_work_dir: str | None = None,
) -> Transport:
    """Resolve the deployment transport (DS-12.3).

    Resolution order:
    1. Explicit --mode flag
    2. Target 'attach' field from lab.yaml
    3. Default: 'direct'

    Args:
        mode: Explicit mode ('gateway' or 'direct') from CLI.
        target_attach: The 'attach' field from lab.yaml target entry.
        gateway_host: SSH hostname for gateway.
        gateway_user: SSH user for gateway.
        gateway_work_dir: Working directory on gateway.

    Returns:
        Either SSHTransport or DirectTransport.
    """
    resolved_mode = mode or target_attach or "direct"

    if resolved_mode == "gateway":
        if not gateway_host:
            print("[cede] ERROR: gateway mode requires --gateway or lab.yaml gateway config", file=sys.stderr)
            raise SystemExit(1)

        ssh_host = f"{gateway_user}@{gateway_host}" if gateway_user else gateway_host
        return SSHTransport(
            ssh_host=ssh_host,
            work_dir=gateway_work_dir or "~/cede",
        )

    return DirectTransport()
