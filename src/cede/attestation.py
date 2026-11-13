"""Generalized firmware attestation using Target Type and App Manifest (DS-9).

Replaces the hardcoded role-based banner checks with a data-driven approach
that derives expected banners from cede_app.yaml and target-type.yaml.
"""

from __future__ import annotations

import os
import re
from typing import Literal


DIGEST_RE = re.compile(rb"digest=([A-Za-z0-9._-]+)", re.IGNORECASE)


def digest_token(buf: bytes) -> bytes | None:
    """Extract the first digest= token from serial output."""
    m = DIGEST_RE.search(buf)
    return m.group(1) if m else None


def banner_prefix_ok(buf: bytes, banner_prefix: str) -> bool:
    """Check if the expected banner prefix appears in the buffer."""
    return banner_prefix.encode("utf-8") in buf


def digest_banner_line(buf: bytes, banner_prefix: str) -> str | None:
    """Find the first line containing both the banner prefix and a digest= token."""
    prefix_lower = banner_prefix.lower()
    for raw in buf.splitlines():
        line = raw.decode("utf-8", errors="replace").strip()
        if prefix_lower in line.lower() and "digest=" in line.lower():
            return line
    return None


def expected_digest_value(cli_digest: str) -> str:
    """Resolve expected digest: CLI arg wins, else CEDE_EXPECT_DIGEST env var."""
    d = (cli_digest or "").strip()
    if d:
        return d
    return (os.environ.get("CEDE_EXPECT_DIGEST") or "").strip()


def attestation_failure_reason(
    buf: bytes,
    *,
    banner_prefix: str,
    digest_must_equal: str = "",
) -> str | None:
    """Check attestation and return None on success, or an error string on failure.

    This is the generalized version that accepts a banner_prefix derived from
    the Target Type or App Manifest rather than a hardcoded role.

    Args:
        buf: Raw serial/stdout output bytes.
        banner_prefix: Expected prefix string (e.g. "CEDE hello_lab rp2 ok").
        digest_must_equal: If non-empty, the digest token must match (case-insensitive).

    Returns:
        None if attestation passes, otherwise a descriptive error string.
    """
    if not banner_prefix_ok(buf, banner_prefix):
        return f"missing banner prefix: {banner_prefix!r} not found in output"

    tok = digest_token(buf)
    if not tok:
        return "banner must include digest=<id> token"

    if digest_must_equal:
        if tok.lower() != digest_must_equal.lower().encode("ascii"):
            return (
                f"digest mismatch: device has digest={tok.decode('ascii', errors='replace')!r}, "
                f"expected digest={digest_must_equal!r}"
            )

    return None


def resolve_banner_prefix(
    *,
    app_banner_prefix: str | None = None,
    target_type_name: str | None = None,
    application_id: str | None = None,
) -> str:
    """Derive the expected banner prefix.

    Resolution order:
    1. Explicit banner_prefix from cede_app.yaml
    2. Constructed from application_id + target type: "CEDE {app_id} {target} ok"
    3. Fallback: "CEDE"
    """
    if app_banner_prefix:
        return app_banner_prefix

    parts = ["CEDE"]
    if application_id:
        parts.append(application_id)
    if target_type_name:
        parts.append(target_type_name)
    parts.append("ok")
    return " ".join(parts)
