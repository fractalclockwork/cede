"""Tests for the transport layer (DS-8, DS-12)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cede.transport import DirectTransport, SSHTransport, resolve_transport


class TestDirectTransport:
    def test_run_command_local(self, tmp_path: Path) -> None:
        t = DirectTransport()
        result = t.run_command(["echo", "hello"], capture_output=True)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_run_command_check_raises(self) -> None:
        t = DirectTransport()
        with pytest.raises(subprocess.CalledProcessError):
            t.run_command(["false"], check=True)

    def test_run_command_no_check(self) -> None:
        t = DirectTransport()
        result = t.run_command(["false"], check=False)
        assert result.returncode != 0

    def test_copy_file(self, tmp_path: Path) -> None:
        t = DirectTransport()
        src = tmp_path / "src" / "firmware.uf2"
        src.parent.mkdir()
        src.write_bytes(b"UF2 data")

        dest = str(tmp_path / "dest" / "firmware.uf2")
        t.copy_file(src, dest)

        assert Path(dest).exists()
        assert Path(dest).read_bytes() == b"UF2 data"

    def test_sync_dir(self, tmp_path: Path) -> None:
        t = DirectTransport()
        src = tmp_path / "src"
        src.mkdir()
        (src / "file1.txt").write_text("hello")
        (src / "sub").mkdir()
        (src / "sub" / "file2.txt").write_text("world")

        dest = str(tmp_path / "dest")
        t.sync_dir(src, dest)

        assert (Path(dest) / "file1.txt").read_text() == "hello"
        assert (Path(dest) / "sub" / "file2.txt").read_text() == "world"


class TestSSHTransport:
    @patch("cede.transport.subprocess.run")
    def test_run_command_wraps_ssh(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n")
        t = SSHTransport(ssh_host="pi@cede-pi.local")

        t.run_command(["ls", "/tmp"], capture_output=True)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ssh"
        assert "pi@cede-pi.local" in call_args
        assert "ls /tmp" in call_args[-1]

    @patch("cede.transport.subprocess.run")
    def test_run_command_with_cwd(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        t = SSHTransport(ssh_host="pi@host")

        t.run_command(["make", "flash"], cwd="/home/pi/cede")

        call_args = mock_run.call_args[0][0]
        assert "cd /home/pi/cede && make flash" in call_args[-1]

    @patch("cede.transport.subprocess.run")
    def test_copy_file_uses_scp(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        t = SSHTransport(ssh_host="pi@host")

        t.copy_file(Path("/tmp/fw.uf2"), "/home/pi/fw.uf2")

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "scp"
        assert "/tmp/fw.uf2" in call_args
        assert "pi@host:/home/pi/fw.uf2" in call_args

    @patch("cede.transport.subprocess.run")
    def test_sync_dir_uses_rsync(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        t = SSHTransport(ssh_host="pi@host")

        t.sync_dir(Path("/local/scripts"), "/remote/scripts")

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "rsync"
        assert "-az" in call_args
        assert "--delete" in call_args
        assert "pi@host:/remote/scripts/" in call_args


class TestResolveTransport:
    def test_explicit_direct_mode(self) -> None:
        t = resolve_transport(mode="direct")
        assert isinstance(t, DirectTransport)

    def test_explicit_gateway_mode(self) -> None:
        t = resolve_transport(mode="gateway", gateway_host="cede-pi.local", gateway_user="pi")
        assert isinstance(t, SSHTransport)
        assert t.ssh_host == "pi@cede-pi.local"

    def test_gateway_mode_without_host_exits(self) -> None:
        with pytest.raises(SystemExit):
            resolve_transport(mode="gateway")

    def test_target_attach_gateway(self) -> None:
        t = resolve_transport(target_attach="gateway", gateway_host="pi.local", gateway_user="pi")
        assert isinstance(t, SSHTransport)

    def test_target_attach_direct(self) -> None:
        t = resolve_transport(target_attach="direct")
        assert isinstance(t, DirectTransport)

    def test_default_is_direct(self) -> None:
        t = resolve_transport()
        assert isinstance(t, DirectTransport)

    def test_mode_overrides_target_attach(self) -> None:
        t = resolve_transport(mode="direct", target_attach="gateway")
        assert isinstance(t, DirectTransport)

    def test_gateway_work_dir(self) -> None:
        t = resolve_transport(mode="gateway", gateway_host="host", gateway_user="u", gateway_work_dir="/opt/cede")
        assert isinstance(t, SSHTransport)
        assert t.work_dir == "/opt/cede"

    def test_gateway_host_without_user(self) -> None:
        t = resolve_transport(mode="gateway", gateway_host="cede-pi.local")
        assert isinstance(t, SSHTransport)
        assert t.ssh_host == "cede-pi.local"
