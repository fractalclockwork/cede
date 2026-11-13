"""Tests for 'cede validate' command (DS-7, DS-9, mocked transport)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cede.target_type import load_target_type
from cede.validate import run_validate


@pytest.fixture
def target_types_dir(repo_root: Path) -> Path:
    return repo_root / "target-types"


@pytest.fixture
def pico_target(target_types_dir: Path):
    return load_target_type("pico", target_types_dir=target_types_dir)


@pytest.fixture
def uno_target(target_types_dir: Path):
    return load_target_type("uno", target_types_dir=target_types_dir)


class TestRunValidate:
    def test_validate_passes_on_matching_digest(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok digest=abc123def456\n",
        )

        result = run_validate(
            target_type=pico_target,
            digest="abc123def456",
            transport=transport,
        )
        assert result is True

    def test_validate_fails_on_digest_mismatch(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok digest=wrongdigest12\n",
        )

        with pytest.raises(SystemExit) as exc_info:
            run_validate(
                target_type=pico_target,
                digest="abc123def456",
                transport=transport,
            )
        assert exc_info.value.code == 1

    def test_validate_fails_on_no_output(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(returncode=0, stdout="")

        with pytest.raises(SystemExit) as exc_info:
            run_validate(
                target_type=pico_target,
                digest="abc123def456",
                transport=transport,
            )
        assert exc_info.value.code == 1

    def test_validate_fails_on_no_digest_in_output(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok\n",
        )

        with pytest.raises(SystemExit) as exc_info:
            run_validate(
                target_type=pico_target,
                digest="abc123def456",
                transport=transport,
            )
        assert exc_info.value.code == 1

    def test_validate_case_insensitive_digest(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok digest=ABC123DEF456\n",
        )

        result = run_validate(
            target_type=pico_target,
            digest="abc123def456",
            transport=transport,
        )
        assert result is True

    def test_validate_with_banner_prefix(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab rp2 ok digest=abc123def456\n",
        )

        result = run_validate(
            target_type=pico_target,
            digest="abc123def456",
            transport=transport,
            banner_prefix="CEDE hello_lab rp2 ok",
        )
        assert result is True

    def test_validate_fails_wrong_banner_prefix(self, pico_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE wrong_app pico ok digest=abc123def456\n",
        )

        with pytest.raises(SystemExit) as exc_info:
            run_validate(
                target_type=pico_target,
                digest="abc123def456",
                transport=transport,
                banner_prefix="CEDE hello_lab rp2 ok",
            )
        assert exc_info.value.code == 1

    def test_validate_uno_target(self, uno_target) -> None:
        transport = MagicMock()
        transport.run_command.return_value = MagicMock(
            returncode=0,
            stdout="CEDE hello_lab ok digest=feedface1234\n",
        )

        result = run_validate(
            target_type=uno_target,
            digest="feedface1234",
            transport=transport,
        )
        assert result is True
