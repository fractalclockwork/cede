"""Tests for 'cede deploy' command (DS-7, mocked transport)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cede.deploy import run_deploy
from cede.target_type import load_target_type
from cede.transport import DirectTransport


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent time.sleep from delaying tests."""
    monkeypatch.setattr("cede.deploy.time.sleep", lambda _: None)


@pytest.fixture
def target_types_dir(repo_root: Path) -> Path:
    return repo_root / "target-types"


@pytest.fixture
def pico_target(target_types_dir: Path):
    return load_target_type("pico", target_types_dir=target_types_dir)


@pytest.fixture
def uno_target(target_types_dir: Path):
    return load_target_type("uno", target_types_dir=target_types_dir)


class TestRunDeploy:
    def test_deploy_copies_and_flashes(self, pico_target, tmp_path: Path) -> None:
        artifact = tmp_path / "hello_lab.uf2"
        artifact.write_bytes(b"UF2 data")

        transport = MagicMock()
        transport.run_command.return_value = MagicMock(returncode=0)

        run_deploy(
            target_type=pico_target,
            artifact=artifact,
            transport=transport,
        )

        transport.copy_file.assert_called_once_with(artifact, "/tmp/hello_lab.uf2")
        assert transport.run_command.call_count >= 1

    def test_deploy_runs_pre_flash(self, pico_target, tmp_path: Path) -> None:
        artifact = tmp_path / "hello_lab.uf2"
        artifact.write_bytes(b"UF2 data")

        transport = MagicMock()
        transport.run_command.return_value = MagicMock(returncode=0)

        run_deploy(target_type=pico_target, artifact=artifact, transport=transport)

        calls = [str(c) for c in transport.run_command.call_args_list]
        pre_flash_called = any("picotool reboot" in c for c in calls)
        assert pre_flash_called, "pre_flash should be invoked for pico"

    def test_deploy_no_pre_flash_for_uno(self, uno_target, tmp_path: Path) -> None:
        artifact = tmp_path / "firmware.hex"
        artifact.write_bytes(b":00000001FF\n")

        transport = MagicMock()
        transport.run_command.return_value = MagicMock(returncode=0)

        run_deploy(target_type=uno_target, artifact=artifact, transport=transport)

        calls = [str(c) for c in transport.run_command.call_args_list]
        assert not any("reboot" in c for c in calls)

    def test_deploy_flash_failure_exits(self, pico_target, tmp_path: Path) -> None:
        artifact = tmp_path / "hello_lab.uf2"
        artifact.write_bytes(b"UF2 data")

        transport = MagicMock()
        transport.run_command.side_effect = [
            MagicMock(returncode=0),  # pre_flash
            MagicMock(returncode=1),  # flash fails
        ]

        with pytest.raises(SystemExit) as exc_info:
            run_deploy(target_type=pico_target, artifact=artifact, transport=transport)
        assert exc_info.value.code == 1

    def test_deploy_missing_artifact_exits(self, pico_target, tmp_path: Path) -> None:
        artifact = tmp_path / "nonexistent.uf2"
        transport = MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            run_deploy(target_type=pico_target, artifact=artifact, transport=transport)
        assert exc_info.value.code == 1

    def test_deploy_flash_command_contains_artifact(self, pico_target, tmp_path: Path) -> None:
        artifact = tmp_path / "hello_lab.uf2"
        artifact.write_bytes(b"UF2")

        transport = MagicMock()
        transport.run_command.return_value = MagicMock(returncode=0)

        run_deploy(target_type=pico_target, artifact=artifact, transport=transport)

        flash_calls = [
            c for c in transport.run_command.call_args_list
            if "/tmp/hello_lab.uf2" in str(c)
        ]
        assert len(flash_calls) >= 1
