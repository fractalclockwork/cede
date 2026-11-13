"""Debug session: serial console or GDB attach (DS-7.1, DS-13)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cede.target_type import TargetType
from cede.transport import Transport


def run_debug_serial(
    *,
    target_type: TargetType,
    transport: Transport,
    port: str | None = None,
    log_file: Path | None = None,
) -> None:
    """Open an interactive serial console session.

    Picks `picocom`, falling back to `minicom -D`, then `screen`. The first
    tool found on PATH wins.
    """
    resolved_port = port or _resolve_port(target_type)
    baud = target_type.serial.speed

    tool = _first_available(["picocom", "minicom", "screen"])
    if not tool:
        print(
            "[cede debug] ERROR: no serial terminal found (install picocom, minicom, or screen)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if tool == "picocom":
        serial_cmd = f"picocom -b {baud} {resolved_port}"
        exit_hint = "Ctrl+A Ctrl+X to exit picocom"
    elif tool == "minicom":
        serial_cmd = f"minicom -b {baud} -D {resolved_port}"
        exit_hint = "Ctrl+A X to exit minicom"
    else:
        serial_cmd = f"screen {resolved_port} {baud}"
        exit_hint = "Ctrl+A K to exit screen"

    print(f"[cede debug] serial: {serial_cmd}", file=sys.stderr)
    print(f"[cede debug] {exit_hint}, or Ctrl+C to abort", file=sys.stderr)

    if log_file:
        serial_cmd += f" | tee {log_file}"

    try:
        subprocess.run(["sh", "-c", serial_cmd], check=False)
    except KeyboardInterrupt:
        print("\n[cede debug] session ended", file=sys.stderr)


def run_debug_gdb(
    *,
    target_type: TargetType,
    transport: Transport,
    port: str | None = None,
    elf_path: Path | None = None,
) -> None:
    """Launch a GDB debug session.

    Composes an `openocd` + `gdb-multiarch` invocation from the target type's
    debug configuration (tool, interface, gdb_port).
    """
    debug = target_type.debug
    if debug.method != "swd" or not debug.tool or not debug.gdb_port:
        print(
            f"[cede debug] ERROR: target type '{target_type.target_type}' has no GDB debug config",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not elf_path:
        print("[cede debug] ERROR: --elf is required for GDB sessions", file=sys.stderr)
        raise SystemExit(1)

    if debug.tool == "openocd":
        interface = debug.interface or "cmsis-dap"
        target_cfg = f"target/{target_type.target_type}.cfg"
        openocd_cmd = (
            f"openocd -f interface/{interface}.cfg -f {target_cfg} "
            f"-c 'gdb_port {debug.gdb_port}'"
        )
    else:
        openocd_cmd = debug.tool
    gdb_cmd = (
        f"{openocd_cmd} & "
        f"sleep 1 && gdb-multiarch -ex 'target remote :{debug.gdb_port}' "
        f"-ex 'load' '{elf_path}'"
    )

    print(f"[cede debug] gdb: {gdb_cmd}", file=sys.stderr)

    try:
        subprocess.run(["sh", "-c", gdb_cmd], check=False)
    except KeyboardInterrupt:
        print("\n[cede debug] session ended", file=sys.stderr)


def _first_available(candidates: list[str]) -> str | None:
    """Return the first command on PATH from candidates, else None."""
    import shutil

    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    return None


def _resolve_port(target_type: TargetType) -> str:
    """Resolve the serial port for the target."""
    dm = target_type.serial.device_match
    if dm.by_id_glob:
        import glob as g
        matches = g.glob(dm.by_id_glob)
        if matches:
            return matches[0]

    if dm.fallback_globs:
        import glob as g
        for pattern in dm.fallback_globs:
            matches = g.glob(pattern)
            if matches:
                return matches[0]

    return "/dev/ttyACM0"
