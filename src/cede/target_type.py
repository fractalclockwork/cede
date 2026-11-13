"""Target Type loader and dataclass (DS-5).

Loads target-types/*.yaml manifests, validates them against the JSON Schema,
and provides a TargetType dataclass for the rest of the CLI to consume.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml


@dataclass(frozen=True)
class DeviceMatch:
    """Serial device discovery rules."""

    by_id_glob: str | None = None
    fallback_globs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolchainConfig:
    """Toolchain container configuration."""

    image: str
    build_command: str
    artifact_pattern: str
    build_context: str = "/workspace"


@dataclass(frozen=True)
class FlashConfig:
    """Flash tool configuration."""

    tool: str
    command: str
    pre_flash: str | None = None
    post_flash_delay_s: float = 0


@dataclass(frozen=True)
class SerialConfig:
    """Serial port configuration."""

    speed: int
    banner_pattern: str
    device_match: DeviceMatch


@dataclass(frozen=True)
class DebugConfig:
    """Debug interface configuration."""

    method: str
    tool: str | None = None
    interface: str | None = None
    gdb_port: int | None = None


@dataclass(frozen=True)
class TargetType:
    """A fully-loaded Target Type manifest (DS-5.2)."""

    target_type: str
    display_name: str
    toolchain: ToolchainConfig
    flash: FlashConfig
    serial: SerialConfig
    debug: DebugConfig | None = None

    def resolve_flash_command(self, *, artifact: str, port: str = "") -> str:
        """Substitute placeholders in flash.command."""
        cmd = self.flash.command
        cmd = cmd.replace("{artifact}", artifact)
        cmd = cmd.replace("{port}", port)
        return cmd

    def resolve_banner_pattern(self, *, digest: str) -> re.Pattern[str]:
        """Compile banner_pattern with {digest} replaced."""
        raw = self.serial.banner_pattern.replace("{digest}", re.escape(digest))
        return re.compile(raw)


def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "target-types" / "target-type.schema.json"


def _target_types_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "target-types"


def load_schema() -> dict[str, Any]:
    """Load the Target Type JSON Schema."""
    with open(_schema_path(), encoding="utf-8") as f:
        return json.load(f)


def load_target_type(name: str, *, target_types_dir: Path | None = None) -> TargetType:
    """Load and validate a single Target Type manifest by name.

    Args:
        name: Target type identifier (e.g. 'pico', 'uno').
        target_types_dir: Override directory containing YAML manifests.

    Returns:
        A validated TargetType instance.

    Raises:
        FileNotFoundError: If the manifest does not exist.
        jsonschema.ValidationError: If the manifest fails schema validation.
    """
    base = target_types_dir or _target_types_dir()
    manifest_path = base / f"{name}.yaml"

    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    schema = load_schema()
    jsonschema.validate(instance=data, schema=schema)

    return _parse_target_type(data)


def load_all_target_types(*, target_types_dir: Path | None = None) -> dict[str, TargetType]:
    """Load all Target Type manifests from the target-types/ directory.

    Returns:
        Dict mapping target_type name to TargetType instance.
    """
    base = target_types_dir or _target_types_dir()
    result: dict[str, TargetType] = {}
    for path in sorted(base.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        schema = load_schema()
        jsonschema.validate(instance=data, schema=schema)
        tt = _parse_target_type(data)
        result[tt.target_type] = tt
    return result


def _parse_target_type(data: dict[str, Any]) -> TargetType:
    """Parse validated YAML dict into a TargetType dataclass."""
    tc = data["toolchain"]
    fl = data["flash"]
    sr = data["serial"]
    dm = sr["device_match"]
    db = data.get("debug")

    return TargetType(
        target_type=data["target_type"],
        display_name=data.get("display_name", data["target_type"]),
        toolchain=ToolchainConfig(
            image=tc["image"],
            build_command=tc["build_command"],
            artifact_pattern=tc["artifact_pattern"],
            build_context=tc.get("build_context", "/workspace"),
        ),
        flash=FlashConfig(
            tool=fl["tool"],
            command=fl["command"],
            pre_flash=fl.get("pre_flash"),
            post_flash_delay_s=fl.get("post_flash_delay_s", 0),
        ),
        serial=SerialConfig(
            speed=sr["speed"],
            banner_pattern=sr["banner_pattern"],
            device_match=DeviceMatch(
                by_id_glob=dm.get("by_id_glob"),
                fallback_globs=dm.get("fallback_globs", []),
            ),
        ),
        debug=DebugConfig(
            method=db["method"],
            tool=db.get("tool"),
            interface=db.get("interface"),
            gdb_port=db.get("gdb_port"),
        ) if db else None,
    )
