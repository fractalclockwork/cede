"""Tests for cede new-app scaffolding (DS-18.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cede.scaffold import scaffold_app


@pytest.fixture
def templates_dir(repo_root: Path) -> Path:
    return repo_root / "templates"


class TestScaffoldPico:
    def test_creates_pico_app(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_sensor",
            target="pico",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        assert result == tmp_path / "my_sensor" / "pico"
        assert result.is_dir()

    def test_creates_cmake(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_sensor",
            target="pico",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        cmake = result / "CMakeLists.txt"
        assert cmake.exists()
        content = cmake.read_text()
        assert "project(my_sensor" in content
        assert "add_executable(my_sensor" in content

    def test_creates_main_c(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_sensor",
            target="pico",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        main = result / "src" / "main.c"
        assert main.exists()
        content = main.read_text()
        assert "my_sensor" in content
        assert "CEDE_IMAGE_ID" in content

    def test_creates_cede_app_yaml(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_sensor",
            target="pico",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        manifest = result / "cede_app.yaml"
        assert manifest.exists()
        data = yaml.safe_load(manifest.read_text())
        assert data["application_id"] == "my_sensor"
        assert data["target"] == "pico"
        assert data["category"] == "user"

    def test_app_name_substituted_everywhere(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="custom_app",
            target="pico",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        for f in result.rglob("*"):
            if f.is_file():
                content = f.read_text()
                assert "{{app_name}}" not in content, f"Unresolved placeholder in {f}"


class TestScaffoldUno:
    def test_creates_uno_app(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_led",
            target="uno",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        assert result == tmp_path / "my_led" / "uno"
        assert result.is_dir()

    def test_creates_ino(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_led",
            target="uno",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        ino = result / "app.ino"
        assert ino.exists()
        content = ino.read_text()
        assert "my_led" in content
        assert "CEDE_IMAGE_ID" in content

    def test_creates_build_id_header(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_led",
            target="uno",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        header = result / "cede_build_id.h"
        assert header.exists()

    def test_creates_manifest(self, tmp_path: Path, templates_dir: Path) -> None:
        result = scaffold_app(
            app_name="my_led",
            target="uno",
            output_dir=tmp_path,
            templates_dir=templates_dir,
        )
        manifest = result / "cede_app.yaml"
        assert manifest.exists()
        data = yaml.safe_load(manifest.read_text())
        assert data["application_id"] == "my_led"
        assert data["target"] == "uno"


class TestScaffoldErrors:
    def test_unsupported_target_exits(self, tmp_path: Path, templates_dir: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            scaffold_app(
                app_name="foo",
                target="esp32",
                output_dir=tmp_path,
                templates_dir=templates_dir,
            )
        assert exc_info.value.code == 1

    def test_existing_dir_exits(self, tmp_path: Path, templates_dir: Path) -> None:
        (tmp_path / "existing" / "pico").mkdir(parents=True)
        with pytest.raises(SystemExit) as exc_info:
            scaffold_app(
                app_name="existing",
                target="pico",
                output_dir=tmp_path,
                templates_dir=templates_dir,
            )
        assert exc_info.value.code == 1
