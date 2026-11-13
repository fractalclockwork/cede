"""Tests for v1-to-v2 lab.yaml migration (DS-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cede.migrate import migrate_file, migrate_v1_to_v2


@pytest.fixture
def v1_data() -> dict:
    return {
        "schema_version": 1,
        "hosts": {
            "dev_host": {"role": "dev-host", "repo_root": "~/src/cede"},
            "pi": {"role": "raspberry-pi-gateway", "ssh_host": "cede-pi.local", "ssh_user": "pi", "repo_root": "~/cede"},
        },
        "serial": {
            "defaults": {"baud": 115200, "newline": "\n", "timeout_s": 2.0},
            "devices": {
                "pico": {"by_id_glob": "/dev/serial/by-id/usb-Raspberry_Pi_*", "fallback_globs": ["/dev/ttyACM*"]},
                "uno": {"by_id_glob": "/dev/serial/by-id/usb-Arduino_*", "fallback_globs": ["/dev/ttyUSB*", "/dev/ttyACM*"]},
            },
        },
        "i2c_matrix": {
            "bus_hz": 100000,
            "probe_address": 66,
            "pairs": [{"initiator": "rpi", "target": "pico", "status": "enabled", "linux_bus": 1, "probe_address": 66, "validation": {"mode": "rpi_master_i2cdev_read", "controller": "rpi", "reg": 0, "expect_byte": 206}}],
        },
    }


class TestMigrateV1ToV2:
    def test_sets_schema_version_2(self, v1_data: dict) -> None:
        v2 = migrate_v1_to_v2(v1_data)
        assert v2["schema_version"] == 2

    def test_converts_gateway(self, v1_data: dict) -> None:
        v2 = migrate_v1_to_v2(v1_data)
        assert v2["gateway"]["ssh_host"] == "cede-pi.local"
        assert v2["gateway"]["ssh_user"] == "pi"
        assert v2["gateway"]["work_dir"] == "~/cede"

    def test_converts_targets(self, v1_data: dict) -> None:
        v2 = migrate_v1_to_v2(v1_data)
        assert "pico" in v2["targets"]
        assert "uno" in v2["targets"]
        assert v2["targets"]["pico"]["type"] == "pico"
        assert v2["targets"]["pico"]["attach"] == "gateway"

    def test_serial_config_in_targets(self, v1_data: dict) -> None:
        v2 = migrate_v1_to_v2(v1_data)
        pico = v2["targets"]["pico"]
        assert pico["serial"]["by_id_glob"] == "/dev/serial/by-id/usb-Raspberry_Pi_*"
        assert "/dev/ttyACM*" in pico["serial"]["fallback_globs"]

    def test_preserves_i2c_matrix(self, v1_data: dict) -> None:
        v2 = migrate_v1_to_v2(v1_data)
        assert v2["i2c_matrix"]["bus_hz"] == 100000
        assert len(v2["i2c_matrix"]["pairs"]) == 1

    def test_direct_attach_when_no_gateway(self) -> None:
        v1_no_pi = {
            "schema_version": 1,
            "hosts": {"dev_host": {"role": "dev-host"}},
            "serial": {"defaults": {"baud": 115200, "newline": "\n", "timeout_s": 2.0}, "devices": {"pico": {"fallback_globs": ["/dev/ttyACM*"]}}},
        }
        v2 = migrate_v1_to_v2(v1_no_pi)
        assert "gateway" not in v2
        assert v2["targets"]["pico"]["attach"] == "direct"

    def test_removes_paths_and_applications(self, v1_data: dict) -> None:
        v1_data["paths"] = {"pico_build": "lab/pico/hello_lab/build"}
        v1_data["applications"] = {"lab_stack": {"targets": {}}}
        v2 = migrate_v1_to_v2(v1_data)
        assert "paths" not in v2
        assert "applications" not in v2


class TestMigrateFile:
    def test_writes_v2_file(self, tmp_path: Path, v1_data: dict) -> None:
        v1_path = tmp_path / "lab.yaml"
        with open(v1_path, "w") as f:
            yaml.dump(v1_data, f)

        result = migrate_file(v1_path)
        assert result.suffix == ".yaml"
        assert result.exists()

        with open(result) as f:
            v2 = yaml.safe_load(f)
        assert v2["schema_version"] == 2

    def test_custom_output_path(self, tmp_path: Path, v1_data: dict) -> None:
        v1_path = tmp_path / "lab.yaml"
        with open(v1_path, "w") as f:
            yaml.dump(v1_data, f)

        out = tmp_path / "new_lab.yaml"
        result = migrate_file(v1_path, out)
        assert result == out
        assert out.exists()

    def test_rejects_already_v2(self, tmp_path: Path) -> None:
        v2_path = tmp_path / "lab.yaml"
        with open(v2_path, "w") as f:
            yaml.dump({"schema_version": 2, "targets": {}}, f)

        with pytest.raises(ValueError, match="already v2"):
            migrate_file(v2_path)
