"""Configuration loading for lab.yaml and cede_app.yaml (DS-10, DS-11)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml


@dataclass(frozen=True)
class GatewayConfig:
    """Gateway connection details from lab.yaml."""

    ssh_host: str
    ssh_user: str
    work_dir: str = "~/cede"


@dataclass(frozen=True)
class TargetEntry:
    """A target entry from lab.yaml v2 targets section."""

    name: str
    type: str
    attach: str = "direct"
    serial_by_id_glob: str | None = None
    serial_fallback_globs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LabConfig:
    """Parsed lab.yaml configuration."""

    schema_version: int
    gateway: GatewayConfig | None = None
    targets: dict[str, TargetEntry] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AppManifest:
    """Parsed cede_app.yaml manifest."""

    application_id: str
    target: str
    category: str
    entrypoint: str
    banner_prefix: str | None = None
    i2c_address: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


def find_repo_root(start: Path | None = None) -> Path:
    """Find the CEDE repository root by searching upward for pyproject.toml."""
    p = (start or Path.cwd()).resolve()
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "target-types").is_dir():
            return parent
    raise FileNotFoundError("Cannot find CEDE repository root (no pyproject.toml + target-types/ found)")


def find_lab_config(repo_root: Path | None = None) -> Path | None:
    """Locate lab.yaml (or lab.example.yaml) from env or repo root."""
    env = os.environ.get("CEDE_LAB_CONFIG")
    if env:
        p = Path(env)
        if p.exists():
            return p

    root = repo_root or find_repo_root()
    override = root / "config" / "lab.yaml"
    if override.exists():
        return override
    example = root / "config" / "lab.example.yaml"
    if example.exists():
        return example
    return None


def load_lab_config(path: Path) -> LabConfig:
    """Load and parse a lab.yaml file.

    Supports both v1 (current) and v2 (DS-10.3) schema formats.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    version = data.get("schema_version", 1)

    if version >= 2:
        return _parse_lab_v2(data)
    return _parse_lab_v1(data)


def _parse_lab_v1(data: dict[str, Any]) -> LabConfig:
    """Parse v1 lab.yaml (current format) into LabConfig."""
    gw = None
    hosts = data.get("hosts", {})
    pi = hosts.get("pi", {})
    if pi:
        gw = GatewayConfig(
            ssh_host=pi.get("ssh_host", ""),
            ssh_user=pi.get("ssh_user", "pi"),
            work_dir=pi.get("repo_root", "~/cede"),
        )

    targets: dict[str, TargetEntry] = {}
    serial_devices = data.get("serial", {}).get("devices", {})
    for name, device in serial_devices.items():
        targets[name] = TargetEntry(
            name=name,
            type=name,
            attach="gateway" if gw else "direct",
            serial_by_id_glob=device.get("by_id_glob"),
            serial_fallback_globs=device.get("fallback_globs", []),
        )

    return LabConfig(
        schema_version=data.get("schema_version", 1),
        gateway=gw,
        targets=targets,
        raw=data,
    )


def _parse_lab_v2(data: dict[str, Any]) -> LabConfig:
    """Parse v2 lab.yaml (DS-10.3) into LabConfig."""
    gw_data = data.get("gateway", {})
    gw = GatewayConfig(
        ssh_host=gw_data.get("ssh_host", ""),
        ssh_user=gw_data.get("ssh_user", "pi"),
        work_dir=gw_data.get("work_dir", "~/cede"),
    ) if gw_data else None

    targets: dict[str, TargetEntry] = {}
    for name, tdata in data.get("targets", {}).items():
        serial = tdata.get("serial", {})
        targets[name] = TargetEntry(
            name=name,
            type=tdata.get("type", name),
            attach=tdata.get("attach", "direct"),
            serial_by_id_glob=serial.get("by_id_glob"),
            serial_fallback_globs=serial.get("fallback_globs", []),
        )

    return LabConfig(
        schema_version=data.get("schema_version", 2),
        gateway=gw,
        targets=targets,
        raw=data,
    )


def load_app_manifest(app_dir: Path) -> AppManifest:
    """Load cede_app.yaml from an application directory.

    Args:
        app_dir: Directory containing cede_app.yaml.

    Raises:
        FileNotFoundError: If cede_app.yaml does not exist.
    """
    manifest_path = app_dir / "cede_app.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No cede_app.yaml in {app_dir}")

    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    resources = data.get("resources", {})
    usb = resources.get("usb_serial", {})
    i2c = resources.get("i2c", {})

    return AppManifest(
        application_id=data["application_id"],
        target=data["target"],
        category=data["category"],
        entrypoint=data["entrypoint"],
        banner_prefix=usb.get("banner_prefix"),
        i2c_address=i2c.get("address"),
        raw=data,
    )
