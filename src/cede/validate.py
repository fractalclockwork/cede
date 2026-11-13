"""Validate step: read serial banner and attest firmware identity (DS-7, DS-9)."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from cede.target_type import TargetType
from cede.transport import Transport


def run_validate(
    *,
    target_type: TargetType,
    digest: str,
    transport: Transport,
    port: str | None = None,
    timeout_s: float = 8.0,
    banner_prefix: str | None = None,
) -> bool:
    """Validate firmware by reading the serial banner.

    1. Open the serial port (or run serial read via transport).
    2. Read lines until banner matches or timeout.
    3. Extract digest= and compare against expected.

    Args:
        target_type: Target Type manifest.
        digest: Expected Build Identity token.
        transport: Transport instance.
        port: Serial port path override.
        timeout_s: Seconds to wait for banner.
        banner_prefix: Expected banner prefix (from cede_app.yaml).

    Returns:
        True if validation passed, False otherwise.

    Raises:
        SystemExit: If validation fails.
    """
    print(f"[cede validate] target={target_type.target_type} expected_digest={digest}", file=sys.stderr)

    serial_output = _read_serial(
        transport=transport,
        target_type=target_type,
        port=port,
        timeout_s=timeout_s,
    )

    if serial_output is None:
        print("[cede validate] FAILED: no serial output (timeout)", file=sys.stderr)
        raise SystemExit(1)

    banner_pat = target_type.resolve_banner_pattern(digest=digest)
    if banner_prefix:
        prefix_found = banner_prefix in serial_output
    else:
        prefix_found = True

    digest_pat = re.compile(r"digest=([A-Za-z0-9._-]+)")
    digest_match = digest_pat.search(serial_output)

    if not digest_match:
        print("[cede validate] FAILED: no digest= found in serial output", file=sys.stderr)
        print(f"[cede validate] output: {serial_output[:200]}", file=sys.stderr)
        raise SystemExit(1)

    actual_digest = digest_match.group(1)

    if actual_digest.lower() != digest.lower():
        print(
            f"[cede validate] FAILED: digest mismatch: got '{actual_digest}', expected '{digest}'",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not prefix_found:
        print(
            f"[cede validate] FAILED: banner prefix '{banner_prefix}' not found",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"[cede validate] PASSED: digest={actual_digest}", file=sys.stderr)
    return True


def _read_serial(
    *,
    transport: Transport,
    target_type: TargetType,
    port: str | None,
    timeout_s: float,
) -> str | None:
    """Read serial output from the target via transport.

    Uses a small pyserial-based inline Python snippet so Pico USB-CDC devices
    are properly opened (DTR toggle), and falls back to `cat` if pyserial
    is unavailable.
    """
    baud = target_type.serial.speed
    dm = target_type.serial.device_match

    if port:
        port_expr = f'PORT="{port}"'
    else:
        candidates: list[str] = []
        if dm.by_id_glob:
            candidates.append(dm.by_id_glob)
        for g in dm.fallback_globs:
            candidates.append(g)
        port_expr = (
            'PORT=""; for g in '
            + " ".join(f"'{c}'" for c in candidates)
            + '; do for f in $(ls -1 $g 2>/dev/null); do PORT="$f"; break 2; done; done'
        )

    py_snippet = (
        "import sys, time\n"
        "try:\n"
        "    import serial\n"
        "except Exception:\n"
        "    sys.exit(2)\n"
        "port = sys.argv[1]\n"
        f"baud = {baud}\n"
        f"deadline = time.monotonic() + {timeout_s:.1f}\n"
        "with serial.Serial(port, baud, timeout=0.2) as ser:\n"
        "    ser.reset_input_buffer()\n"
        "    ser.dtr = False\n"
        "    time.sleep(0.05)\n"
        "    ser.dtr = True\n"
        "    buf = b''\n"
        "    while time.monotonic() < deadline:\n"
        "        buf += ser.read(4096)\n"
        "        if b'digest=' in buf:\n"
        "            break\n"
        "        time.sleep(0.05)\n"
        "sys.stdout.buffer.write(buf)\n"
    )

    read_cmd = [
        "sh", "-c",
        (
            f"{port_expr}; "
            "if [ -z \"$PORT\" ]; then echo 'no port matched' >&2; exit 0; fi; "
            f"python3 -c {_shquote(py_snippet)} \"$PORT\" 2>/dev/null || "
            f"timeout {timeout_s:.0f} cat \"$PORT\" 2>/dev/null || true"
        ),
    ]

    result = transport.run_command(read_cmd, check=False, capture_output=True)
    if result.stdout:
        return result.stdout
    return None


def _shquote(s: str) -> str:
    import shlex

    return shlex.quote(s)
