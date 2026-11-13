"""Tests for the Target Type Python loader (DS-5.2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cede.target_type import (
    DebugConfig,
    DeviceMatch,
    FlashConfig,
    SerialConfig,
    TargetType,
    ToolchainConfig,
    load_all_target_types,
    load_target_type,
)


@pytest.fixture
def target_types_dir(repo_root: Path) -> Path:
    return repo_root / "target-types"


class TestLoadTargetType:
    def test_load_pico(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        assert isinstance(tt, TargetType)
        assert tt.target_type == "pico"
        assert "RP2040" in tt.display_name

    def test_load_uno(self, target_types_dir: Path) -> None:
        tt = load_target_type("uno", target_types_dir=target_types_dir)
        assert isinstance(tt, TargetType)
        assert tt.target_type == "uno"
        assert "ATmega328P" in tt.display_name

    def test_nonexistent_raises_file_not_found(self, target_types_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_target_type("esp32", target_types_dir=target_types_dir)

    def test_toolchain_config(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        assert isinstance(tt.toolchain, ToolchainConfig)
        assert tt.toolchain.image == "cede/pico-dev:local"
        assert "cmake" in tt.toolchain.build_command.lower() or "ninja" in tt.toolchain.build_command.lower()
        assert tt.toolchain.artifact_pattern == "build/*.uf2"
        assert tt.toolchain.build_context == "/workspace"

    def test_flash_config(self, target_types_dir: Path) -> None:
        tt = load_target_type("uno", target_types_dir=target_types_dir)
        assert isinstance(tt.flash, FlashConfig)
        assert tt.flash.tool == "avrdude"
        assert "{artifact}" in tt.flash.command
        assert "{port}" in tt.flash.command
        assert tt.flash.post_flash_delay_s == 2

    def test_serial_config(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        assert isinstance(tt.serial, SerialConfig)
        assert tt.serial.speed == 115200
        assert "{digest}" in tt.serial.banner_pattern
        assert isinstance(tt.serial.device_match, DeviceMatch)
        assert tt.serial.device_match.by_id_glob is not None
        assert len(tt.serial.device_match.fallback_globs) >= 1

    def test_debug_config_pico(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        assert tt.debug is not None
        assert isinstance(tt.debug, DebugConfig)
        assert tt.debug.method == "swd"
        assert tt.debug.tool == "openocd"

    def test_debug_config_uno_is_none_method(self, target_types_dir: Path) -> None:
        tt = load_target_type("uno", target_types_dir=target_types_dir)
        assert tt.debug is not None
        assert tt.debug.method == "none"


class TestLoadAllTargetTypes:
    def test_returns_dict_of_target_types(self, target_types_dir: Path) -> None:
        all_tt = load_all_target_types(target_types_dir=target_types_dir)
        assert isinstance(all_tt, dict)
        assert "pico" in all_tt
        assert "uno" in all_tt
        assert len(all_tt) >= 2

    def test_keys_match_target_type_field(self, target_types_dir: Path) -> None:
        all_tt = load_all_target_types(target_types_dir=target_types_dir)
        for key, tt in all_tt.items():
            assert key == tt.target_type


class TestPlaceholderResolution:
    def test_resolve_flash_command(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        cmd = tt.resolve_flash_command(artifact="/tmp/fw.uf2", port="/dev/ttyACM0")
        assert "/tmp/fw.uf2" in cmd
        assert "{artifact}" not in cmd

    def test_resolve_flash_command_uno_has_port(self, target_types_dir: Path) -> None:
        tt = load_target_type("uno", target_types_dir=target_types_dir)
        cmd = tt.resolve_flash_command(artifact="/tmp/fw.hex", port="/dev/ttyUSB0")
        assert "/dev/ttyUSB0" in cmd
        assert "/tmp/fw.hex" in cmd

    def test_resolve_banner_pattern(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        pat = tt.resolve_banner_pattern(digest="abc123def456")
        assert isinstance(pat, re.Pattern)
        assert pat.match("CEDE hello_lab rp2 ok digest=abc123def456")
        assert not pat.match("CEDE hello_lab rp2 ok digest=WRONG")

    def test_banner_pattern_escapes_digest_special_chars(self, target_types_dir: Path) -> None:
        tt = load_target_type("pico", target_types_dir=target_types_dir)
        pat = tt.resolve_banner_pattern(digest="a.b+c")
        assert not pat.match("CEDE hello_lab rp2 ok digest=aXb+c")
