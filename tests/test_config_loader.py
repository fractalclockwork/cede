"""Tests for config.py lab/app config loading (DS-10, DS-11)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cede.config import (
    AppManifest,
    GatewayConfig,
    LabConfig,
    TargetEntry,
    find_lab_config,
    find_repo_root,
    load_app_manifest,
    load_lab_config,
)


class TestFindRepoRoot:
    def test_finds_from_cwd(self, repo_root: Path) -> None:
        found = find_repo_root(repo_root / "tests")
        assert found == repo_root

    def test_finds_from_nested(self, repo_root: Path) -> None:
        found = find_repo_root(repo_root / "src" / "cede")
        assert found == repo_root

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            find_repo_root(tmp_path)


class TestFindLabConfig:
    def test_finds_example(self, repo_root: Path) -> None:
        path = find_lab_config(repo_root)
        assert path is not None
        assert path.name in ("lab.yaml", "lab.example.yaml")

    def test_env_override(self, repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = tmp_path / "custom_lab.yaml"
        custom.write_text("schema_version: 1\nhosts: {}\nserial: {devices: {}}\n")
        monkeypatch.setenv("CEDE_LAB_CONFIG", str(custom))
        path = find_lab_config(repo_root)
        assert path == custom


class TestLoadLabConfigV1:
    def test_loads_example(self, repo_root: Path) -> None:
        path = repo_root / "config" / "lab.example.yaml"
        config = load_lab_config(path)
        assert isinstance(config, LabConfig)
        assert config.schema_version == 1

    def test_gateway_parsed(self, repo_root: Path) -> None:
        path = repo_root / "config" / "lab.example.yaml"
        config = load_lab_config(path)
        assert config.gateway is not None
        assert config.gateway.ssh_host == "cede-pi.local"

    def test_targets_from_serial_devices(self, repo_root: Path) -> None:
        path = repo_root / "config" / "lab.example.yaml"
        config = load_lab_config(path)
        assert "pico" in config.targets
        assert "uno" in config.targets


class TestLoadAppManifest:
    def test_loads_hello_lab_pico(self, repo_root: Path) -> None:
        app_dir = repo_root / "validation-apps" / "hello_lab" / "pico"
        manifest = load_app_manifest(app_dir)
        assert isinstance(manifest, AppManifest)
        assert manifest.application_id == "hello_lab"
        assert manifest.target == "pico"
        assert manifest.category == "validation"

    def test_loads_lab_stack_uno(self, repo_root: Path) -> None:
        app_dir = repo_root / "demo-apps" / "lab_stack" / "uno"
        manifest = load_app_manifest(app_dir)
        assert manifest.application_id == "lab_stack"
        assert manifest.target == "uno"
        assert manifest.category == "user"

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_app_manifest(tmp_path)

    def test_banner_prefix_extracted(self, repo_root: Path) -> None:
        app_dir = repo_root / "validation-apps" / "hello_lab" / "pico"
        manifest = load_app_manifest(app_dir)
        assert manifest.banner_prefix is not None
        assert "CEDE" in manifest.banner_prefix
