"""Tests for lab.yaml v2 schema and config loading (DS-10)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from cede.config import LabConfig, load_lab_config


@pytest.fixture
def v2_schema(repo_root: Path) -> dict:
    schema_path = repo_root / "config" / "lab.v2.schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def v2_example(repo_root: Path) -> dict:
    example_path = repo_root / "config" / "lab.v2.example.yaml"
    with open(example_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def v2_example_path(repo_root: Path) -> Path:
    return repo_root / "config" / "lab.v2.example.yaml"


class TestV2SchemaValidation:
    def test_example_validates(self, v2_schema: dict, v2_example: dict) -> None:
        jsonschema.validate(v2_example, v2_schema)

    def test_schema_requires_version_2(self, v2_schema: dict) -> None:
        bad = {"schema_version": 1, "targets": {"pico": {"type": "pico", "attach": "direct"}}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, v2_schema)

    def test_schema_requires_targets(self, v2_schema: dict) -> None:
        bad = {"schema_version": 2}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, v2_schema)

    def test_target_requires_type_and_attach(self, v2_schema: dict) -> None:
        bad = {"schema_version": 2, "targets": {"pico": {"type": "pico"}}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, v2_schema)

    def test_attach_must_be_valid(self, v2_schema: dict) -> None:
        bad = {"schema_version": 2, "targets": {"pico": {"type": "pico", "attach": "wireless"}}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, v2_schema)

    def test_gateway_requires_ssh_host(self, v2_schema: dict) -> None:
        bad = {"schema_version": 2, "targets": {"pico": {"type": "pico", "attach": "direct"}}, "gateway": {"ssh_user": "pi"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, v2_schema)

    def test_minimal_valid(self, v2_schema: dict) -> None:
        minimal = {"schema_version": 2, "targets": {"pico": {"type": "pico", "attach": "direct"}}}
        jsonschema.validate(minimal, v2_schema)


class TestV2ConfigLoading:
    def test_loads_v2_example(self, v2_example_path: Path) -> None:
        config = load_lab_config(v2_example_path)
        assert isinstance(config, LabConfig)
        assert config.schema_version == 2

    def test_gateway_parsed(self, v2_example_path: Path) -> None:
        config = load_lab_config(v2_example_path)
        assert config.gateway is not None
        assert config.gateway.ssh_host == "cede-pi.local"
        assert config.gateway.ssh_user == "pi"
        assert config.gateway.work_dir == "~/cede"

    def test_targets_parsed(self, v2_example_path: Path) -> None:
        config = load_lab_config(v2_example_path)
        assert "pico" in config.targets
        assert "uno" in config.targets
        assert config.targets["pico"].type == "pico"
        assert config.targets["pico"].attach == "gateway"
        assert config.targets["uno"].attach == "gateway"

    def test_serial_config_in_targets(self, v2_example_path: Path) -> None:
        config = load_lab_config(v2_example_path)
        pico = config.targets["pico"]
        assert pico.serial_by_id_glob == "/dev/serial/by-id/usb-Raspberry_Pi_*"
        assert "/dev/ttyACM*" in pico.serial_fallback_globs

    def test_v1_example_still_loads(self, repo_root: Path) -> None:
        v1_path = repo_root / "config" / "lab.example.yaml"
        config = load_lab_config(v1_path)
        assert config.schema_version == 1
        assert config.gateway is not None
        assert "pico" in config.targets
