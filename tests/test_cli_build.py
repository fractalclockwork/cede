"""Tests for 'cede build' command (DS-7, mocked Docker subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cede.build import run_build, _find_artifact
from cede.cli import main
from cede.identity import generate_build_identity, read_digest_sidecar, write_digest_sidecar
from cede.target_type import load_target_type


@pytest.fixture
def target_types_dir(repo_root: Path) -> Path:
    return repo_root / "target-types"


@pytest.fixture
def pico_target(target_types_dir: Path):
    return load_target_type("pico", target_types_dir=target_types_dir)


class TestBuildIdentity:
    def test_generate_from_git(self, repo_root: Path) -> None:
        digest = generate_build_identity(repo_root)
        assert len(digest) == 12
        assert digest.isalnum()

    def test_generate_nogit_fallback(self, tmp_path: Path) -> None:
        digest = generate_build_identity(tmp_path)
        assert digest == "nogit"

    def test_write_and_read_sidecar(self, tmp_path: Path) -> None:
        artifact = tmp_path / "firmware.uf2"
        artifact.write_bytes(b"fake firmware")

        sidecar = write_digest_sidecar(artifact, "abc123def456")
        assert sidecar.exists()
        assert sidecar.name == "firmware.uf2.digest"

        read_back = read_digest_sidecar(artifact)
        assert read_back == "abc123def456"

    def test_read_sidecar_missing(self, tmp_path: Path) -> None:
        artifact = tmp_path / "firmware.uf2"
        artifact.write_bytes(b"fake")
        assert read_digest_sidecar(artifact) is None


class TestFindArtifact:
    def test_finds_uf2(self, tmp_path: Path) -> None:
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        uf2 = build_dir / "hello_lab.uf2"
        uf2.write_bytes(b"UF2")
        result = _find_artifact(tmp_path, "build/*.uf2")
        assert result == uf2

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        result = _find_artifact(tmp_path, "build/*.uf2")
        assert result is None

    def test_finds_hex(self, tmp_path: Path) -> None:
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        hex_file = build_dir / "firmware.hex"
        hex_file.write_text(":00000001FF\n")
        result = _find_artifact(tmp_path, "build/*.hex")
        assert result == hex_file


class TestRunBuild:
    @patch("cede.build.subprocess.run")
    def test_successful_build(self, mock_run: MagicMock, pico_target, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        artifact = build_dir / "hello_lab.uf2"
        artifact.write_bytes(b"UF2 content")

        result = run_build(
            target_type=pico_target,
            app_dir=tmp_path,
            workspace=tmp_path,
            digest="test123digest",
        )

        assert result == artifact
        assert mock_run.call_count >= 1
        call_args = mock_run.call_args_list[0][0][0]
        assert "docker" in call_args[0]
        assert "CEDE_IMAGE_ID=test123digest" in " ".join(call_args)

    @patch("cede.build.subprocess.run")
    def test_build_failure_exits(self, mock_run: MagicMock, pico_target, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1)

        with pytest.raises(SystemExit) as exc_info:
            run_build(
                target_type=pico_target,
                app_dir=tmp_path,
                workspace=tmp_path,
                digest="test123",
            )
        assert exc_info.value.code == 1

    @patch("cede.build.subprocess.run")
    def test_no_artifact_exits(self, mock_run: MagicMock, pico_target, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with pytest.raises(SystemExit) as exc_info:
            run_build(
                target_type=pico_target,
                app_dir=tmp_path,
                workspace=tmp_path,
                digest="test123",
            )
        assert exc_info.value.code == 1

    @patch("cede.build.subprocess.run")
    def test_writes_digest_sidecar(self, mock_run: MagicMock, pico_target, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        artifact = build_dir / "hello_lab.uf2"
        artifact.write_bytes(b"UF2 content")

        run_build(
            target_type=pico_target,
            app_dir=tmp_path,
            workspace=tmp_path,
            digest="mydigest12ab",
        )

        sidecar = artifact.with_suffix(".uf2.digest")
        assert sidecar.exists()
        assert sidecar.read_text().strip() == "mydigest12ab"


class TestCLIBuildCommand:
    def test_build_help_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["build", "--help"])
        assert exc_info.value.code == 0

    def test_build_requires_target(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["build"])
        assert exc_info.value.code == 2

    def test_version(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
