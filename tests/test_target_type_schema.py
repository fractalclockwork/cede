"""Validate target-types/*.yaml manifests against the Target Type JSON Schema (DS-5.3)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml


@pytest.fixture
def target_types_dir(repo_root: Path) -> Path:
    return repo_root / "target-types"


@pytest.fixture
def schema(target_types_dir: Path) -> dict:
    schema_path = target_types_dir / "target-type.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def _all_manifests(target_types_dir: Path) -> list[Path]:
    return sorted(target_types_dir.glob("*.yaml"))


def test_at_least_two_target_types_exist(target_types_dir: Path) -> None:
    manifests = _all_manifests(target_types_dir)
    assert len(manifests) >= 2, "DS-5.4: CEDE ships with at least pico and uno"


@pytest.mark.parametrize("name", ["pico", "uno"])
def test_required_target_type_exists(target_types_dir: Path, name: str) -> None:
    assert (target_types_dir / f"{name}.yaml").exists()


@pytest.mark.parametrize("name", ["pico", "uno"])
def test_target_type_validates_against_schema(
    target_types_dir: Path, schema: dict, name: str,
) -> None:
    manifest_path = target_types_dir / f"{name}.yaml"
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    jsonschema.validate(instance=data, schema=schema)


@pytest.mark.parametrize("name", ["pico", "uno"])
def test_target_type_has_required_fields(target_types_dir: Path, name: str) -> None:
    """DS-5.3: every Target Type manifest MUST provide these fields."""
    manifest_path = target_types_dir / f"{name}.yaml"
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["target_type"] == name
    assert "image" in data["toolchain"]
    assert "build_command" in data["toolchain"]
    assert "artifact_pattern" in data["toolchain"]
    assert "tool" in data["flash"]
    assert "command" in data["flash"]
    assert "speed" in data["serial"]
    assert "banner_pattern" in data["serial"]
    assert "device_match" in data["serial"]


def test_pico_flash_uses_picotool(target_types_dir: Path) -> None:
    with open(target_types_dir / "pico.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["flash"]["tool"] == "picotool"


def test_uno_flash_uses_avrdude(target_types_dir: Path) -> None:
    with open(target_types_dir / "uno.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["flash"]["tool"] == "avrdude"


def test_flash_command_has_artifact_placeholder(target_types_dir: Path, schema: dict) -> None:
    """All flash commands must include {artifact} placeholder."""
    for path in _all_manifests(target_types_dir):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "{artifact}" in data["flash"]["command"], f"{path.name}: missing {{artifact}}"


def test_banner_pattern_has_digest_placeholder(target_types_dir: Path) -> None:
    """All banner patterns must include {digest} placeholder."""
    for path in _all_manifests(target_types_dir):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "{digest}" in data["serial"]["banner_pattern"], f"{path.name}: missing {{digest}}"
