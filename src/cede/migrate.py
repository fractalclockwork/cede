"""Migrate lab.yaml from v1 to v2 format (DS-10.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def migrate_v1_to_v2(v1_data: dict[str, Any]) -> dict[str, Any]:
    """Convert a v1 lab.yaml dict to v2 format.

    Transforms:
    - hosts.pi -> gateway
    - serial.devices -> per-target serial config
    - paths/applications/targets -> removed (resolved by cede_app.yaml + target-types)
    - i2c_matrix -> preserved
    - raspberry_pi_bootstrap -> preserved
    """
    v2: dict[str, Any] = {"schema_version": 2}

    hosts = v1_data.get("hosts", {})
    pi = hosts.get("pi", {})
    if pi:
        v2["gateway"] = {
            "ssh_host": pi.get("ssh_host", ""),
            "ssh_user": pi.get("ssh_user", "pi"),
            "work_dir": pi.get("repo_root", "~/cede"),
        }

    serial_devices = v1_data.get("serial", {}).get("devices", {})
    v2_targets: dict[str, Any] = {}

    for name, device in serial_devices.items():
        attach = "gateway" if pi else "direct"
        target_entry: dict[str, Any] = {
            "type": name,
            "attach": attach,
        }
        serial_conf: dict[str, Any] = {}
        if device.get("by_id_glob"):
            serial_conf["by_id_glob"] = device["by_id_glob"]
        if device.get("fallback_globs"):
            serial_conf["fallback_globs"] = device["fallback_globs"]
        if serial_conf:
            target_entry["serial"] = serial_conf

        v2_targets[name] = target_entry

    v2["targets"] = v2_targets

    if "i2c_matrix" in v1_data:
        v2["i2c_matrix"] = v1_data["i2c_matrix"]

    if "raspberry_pi_bootstrap" in v1_data:
        v2["raspberry_pi_bootstrap"] = v1_data["raspberry_pi_bootstrap"]

    return v2


def migrate_file(input_path: Path, output_path: Path | None = None) -> Path:
    """Read a v1 lab.yaml, convert to v2, and write to output_path.

    Args:
        input_path: Path to existing v1 lab.yaml.
        output_path: Where to write v2. Defaults to input_path with .v2.yaml suffix.

    Returns:
        Path to the written v2 file.
    """
    with open(input_path, encoding="utf-8") as f:
        v1_data = yaml.safe_load(f)

    if v1_data.get("schema_version", 1) >= 2:
        raise ValueError(f"{input_path} is already v2 or later")

    v2_data = migrate_v1_to_v2(v1_data)

    if output_path is None:
        output_path = input_path.with_suffix(".v2.yaml")

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(v2_data, f, default_flow_style=False, sort_keys=False)

    return output_path
