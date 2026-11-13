"""Validate all cede_app.yaml files against the Application Manifest schema (DS-11)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml


@pytest.fixture
def app_schema(repo_root: Path) -> dict:
    schema_path = repo_root / "config" / "cede-app.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def _find_all_app_manifests(repo_root: Path) -> list[Path]:
    """Find every cede_app.yaml in validation-apps/ and demo-apps/."""
    manifests = []
    for base in ("validation-apps", "demo-apps"):
        manifests.extend(sorted((repo_root / base).rglob("cede_app.yaml")))
    return manifests


def test_schema_file_exists(repo_root: Path) -> None:
    assert (repo_root / "config" / "cede-app.schema.json").exists()


def test_at_least_six_app_manifests_exist(repo_root: Path) -> None:
    manifests = _find_all_app_manifests(repo_root)
    assert len(manifests) >= 6, f"Expected >= 6 manifests, found {len(manifests)}"



class TestAllManifestsValid:
    """Each cede_app.yaml must validate against the schema."""

    @pytest.fixture
    def all_manifests(self, repo_root: Path) -> list[Path]:
        return _find_all_app_manifests(repo_root)

    def test_all_validate(self, all_manifests: list[Path], app_schema: dict) -> None:
        errors = []
        for path in all_manifests:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            try:
                jsonschema.validate(instance=data, schema=app_schema)
            except jsonschema.ValidationError as e:
                errors.append(f"{path}: {e.message}")
        assert not errors, "\n".join(errors)


class TestManifestContent:
    """Verify key fields across all manifests."""

    @pytest.fixture
    def manifests(self, repo_root: Path) -> list[tuple[Path, dict]]:
        result = []
        for path in _find_all_app_manifests(repo_root):
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            result.append((path, data))
        return result

    def test_all_have_application_id(self, manifests: list[tuple[Path, dict]]) -> None:
        for path, data in manifests:
            assert "application_id" in data, f"{path}: missing application_id"

    def test_all_have_category(self, manifests: list[tuple[Path, dict]]) -> None:
        for path, data in manifests:
            assert data["category"] in ("validation", "user", "gateway"), (
                f"{path}: invalid category {data.get('category')}"
            )

    def test_all_have_entrypoint(self, manifests: list[tuple[Path, dict]]) -> None:
        for path, data in manifests:
            assert "entrypoint" in data, f"{path}: missing entrypoint"

    def test_validation_apps_are_category_validation(self, repo_root: Path) -> None:
        for path in sorted((repo_root / "validation-apps").rglob("cede_app.yaml")):
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["category"] == "validation", (
                f"{path}: validation app must have category=validation"
            )

    def test_gateway_apps_target_pi(self, manifests: list[tuple[Path, dict]]) -> None:
        for path, data in manifests:
            if data["category"] == "gateway":
                assert data["target"] == "pi", (
                    f"{path}: gateway apps must target 'pi'"
                )

    def test_mcu_apps_have_serial_banner(self, manifests: list[tuple[Path, dict]]) -> None:
        for path, data in manifests:
            if data["category"] in ("validation", "user"):
                resources = data.get("resources", {})
                usb = resources.get("usb_serial", {})
                assert "banner_prefix" in usb, (
                    f"{path}: MCU apps should declare usb_serial.banner_prefix"
                )
