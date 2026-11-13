"""Tests for composite commands: flash-test, run (DS-7.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cede.composite import run_flash_test, run_full
from cede.target_type import load_target_type


@pytest.fixture
def pico_target(repo_root: Path):
    return load_target_type("pico", target_types_dir=repo_root / "target-types")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cede.deploy.time.sleep", lambda _: None)


class TestRunFlashTest:
    def test_calls_deploy_then_validate(self, pico_target, tmp_path: Path) -> None:
        artifact = tmp_path / "hello_lab.uf2"
        artifact.write_bytes(b"UF2")
        sidecar = artifact.with_suffix(".uf2.digest")
        sidecar.write_text("testdigest123\n")

        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok digest=testdigest123\n",
        )

        run_flash_test(
            target_type=pico_target,
            artifact=artifact,
            transport=transport,
        )

        assert transport.copy_file.called
        assert transport.run_command.call_count >= 2

    def test_missing_artifact_exits(self, pico_target, tmp_path: Path) -> None:
        transport = MagicMock()
        with pytest.raises(SystemExit):
            run_flash_test(
                target_type=pico_target,
                artifact=tmp_path / "missing.uf2",
                transport=transport,
            )


class TestRunFull:
    @patch("cede.build.subprocess.run")
    def test_calls_build_deploy_validate(self, mock_docker_run, pico_target, tmp_path: Path) -> None:
        mock_docker_run.return_value = MagicMock(returncode=0)

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        artifact = build_dir / "hello_lab.uf2"
        artifact.write_bytes(b"UF2")

        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok digest=testdigest123\n",
        )

        run_full(
            target_type=pico_target,
            app_dir=tmp_path,
            workspace=tmp_path,
            transport=transport,
            digest="testdigest123",
        )

        assert mock_docker_run.call_count >= 1
        assert transport.copy_file.called
