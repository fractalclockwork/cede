"""Golden documentation commands (config/doc_command_golden.yaml).

Validates that documented ``make`` targets and lightweight shell snippets stay
in sync with CI and remain dry-runnable (``make -n``) without a live bench.

See ``config/doc_command_golden.yaml`` for ``kind: env | artifact | hw``.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "config" / "doc_command_golden.yaml"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "cede-smoke.yml"


def _load_golden() -> dict:
    data = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert data.get("version") == 1
    return data


def _make_dry_cmd(cmd: str) -> str:
    """Prefix a single make invocation with ``-n`` (dry run)."""
    cmd = cmd.strip()
    if not cmd.startswith("make"):
        raise ValueError(f"Expected make-based cmd, got: {cmd!r}")
    return "make -n " + cmd[len("make") :].lstrip()


def _run_shell(cmd: str, *, cwd: Path, env: dict | None = None) -> None:
    merged = {**os.environ, **(env or {})}
    subprocess.run(cmd, shell=True, check=True, cwd=cwd, env=merged)


@pytest.fixture(scope="module")
def golden() -> dict:
    return _load_golden()


def test_cede_smoke_make_lines_match_workflow(golden: dict) -> None:
    wf = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = wf["jobs"]["docker-smoke"]["steps"]
    step = next(
        s
        for s in steps
        if s.get("name") == "Build images and run smoke checks"
    )
    run = textwrap.dedent(step["run"]).strip()
    actual = [ln.strip() for ln in run.splitlines() if ln.strip()]
    expected = golden["cede_smoke_make_lines"]
    assert actual == expected, (
        "cede-smoke.yml 'Build images…' run block changed; update "
        "config/doc_command_golden.yaml 'cede_smoke_make_lines' to match:\n"
        f"  workflow: {actual!r}\n  golden:   {expected!r}"
    )


def test_cede_smoke_pytest_step_uses_expected_compose(golden: dict) -> None:
    wf = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = wf["jobs"]["docker-smoke"]["steps"]
    step = next(
        s for s in steps if s.get("name") == "Pytest (config validation + Hello Lab scaffold)"
    )
    run = textwrap.dedent(step["run"]).strip().replace("\\\n", " ")
    run = re.sub(r"\s+", " ", run)
    compose_file = golden["cede_smoke_compose_file"]
    service = golden["cede_smoke_compose_service"]
    inner = golden["cede_smoke_compose_inner"]
    assert f"-f {compose_file}" in run, run
    assert service in run, run
    assert inner in run.replace("'", ""), run


@pytest.mark.parametrize(
    "entry_id",
    [
        pytest.param(e["id"], id=e["id"])
        for e in _load_golden()["entries"]
        if e.get("check") == "make_n"
    ],
)
def test_golden_make_n(entry_id: str, golden: dict) -> None:
    entry = next(e for e in golden["entries"] if e["id"] == entry_id)
    cwd = REPO_ROOT / entry.get("cwd", ".")
    cmd = entry["cmd"]
    dry = _make_dry_cmd(cmd)
    _run_shell(dry, cwd=cwd.resolve())


@pytest.mark.parametrize(
    "entry_id",
    [
        pytest.param(e["id"], id=e["id"])
        for e in _load_golden()["entries"]
        if e.get("check") == "shell"
    ],
)
def test_golden_shell(entry_id: str, golden: dict) -> None:
    entry = next(e for e in golden["entries"] if e["id"] == entry_id)
    cwd = REPO_ROOT / entry.get("cwd", ".")
    _run_shell(entry["cmd"], cwd=cwd.resolve())


def test_compose_file_referenced_in_golden_exists(golden: dict) -> None:
    rel = Path(golden["cede_smoke_compose_file"])
    assert (REPO_ROOT / rel).is_file(), f"Missing compose file: {rel}"


def test_compose_config_succeeds(golden: dict) -> None:
    compose = golden["cede_smoke_compose_file"]
    if not shutil.which("docker"):
        pytest.skip("docker not on PATH")
    cmd = shlex.join(
        [
            "docker",
            "compose",
            "-f",
            str(REPO_ROOT / compose),
            "config",
            "--quiet",
        ]
    )
    subprocess.run(cmd, shell=True, check=True, cwd=REPO_ROOT)


def test_artifact_expected_paths_when_all_present(golden: dict) -> None:
    rels = golden.get("artifact_expected_paths") or []
    paths = [REPO_ROOT / p for p in rels]
    if not paths:
        pytest.skip("no artifact_expected_paths in golden file")
    if not all(p.is_file() for p in paths):
        pytest.skip(
            "hello_lab / hello_gateway build outputs not present "
            "(expected after e.g. make bootstrap-stage-dev-host with Docker)"
        )
    missing = [str(p.relative_to(REPO_ROOT)) for p in paths if not p.is_file()]
    assert not missing, f"expected artifact paths missing: {missing}"
