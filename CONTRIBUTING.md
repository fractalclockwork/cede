# Contributing to CEDE

Thanks for your interest in CEDE! This guide covers the basics of setting up a development environment, running tests, and submitting changes.

## Dev Environment Setup

### Prerequisites

- **Docker** (for building firmware and running toolchain containers)
- **[uv](https://docs.astral.sh/uv/)** (Python package manager for local validation)
- **GNU Make**

### Local Setup

```bash
uv sync                    # install Python deps (main + dev groups)
make validate              # pytest tests/ excluding @pytest.mark.hardware (Dev-Host / contracts)
```

For Docker toolchains:

```bash
make -C lab/docker build-images   # build pico-dev, arduino-dev, orchestration-dev
make -C lab/docker smoke          # toolchain smoke checks
```

### Lab Configuration

Copy `config/lab.example.yaml` to `config/lab.yaml` and fill in your machine-specific values (SSH hosts, serial device globs). `config/lab.yaml` is gitignored (`lab/config/` is a symlink to `config/`).

## Running Tests

| Command | Scope |
|---------|-------|
| `make validate` | Pytest on `tests/` with **`-m "not hardware"`** (config, CLI, cloud-init, transport, **no** `@pytest.mark.hardware` tests) |
| `make validate-target` | Pytest **`-m hardware`** on `tests/` — digest smokes / matrix stubs; set **`CEDE_RUN_HARDWARE_FULL`**, **`CEDE_RUN_HARDWARE_PICO`**, or **`CEDE_RUN_HARDWARE_UNO`** on a bench |
| `make validation-targets` | Bench: build **`hello_lab`** (Pico/Uno) + **`hello_gateway`** (Pi) with the same digest, deploy each, assert attestation banners (Docker + **`GATEWAY`** + devices; optional **`UNO_PORT`**) |
| `make test-config-local` | Schema validation only |
| `make pi-test-cloud-init` | Cloud-init render test |
| `make container-test-baseline` | CI-equivalent: Docker build + smoke + firmware + **env-only** pytest in `orchestration-dev` (same `-m "not hardware"` as `make validate`) |

**Per-target validation map:** For a single table of *what to run* for Dev-Host contracts, Docker toolchains, Pi as SSH gateway, Pi as **`hello_gateway`** native target, Pico, Uno, one-shot tri-target (**`make validation-targets`**), and I2C—plus how **`make validate`**, **`make validate-target`**, **`cede validate`**, and **`make pi-gateway-*`** differ—see [docs/USER_GUIDE.md §2.1](docs/USER_GUIDE.md#21-validation-by-target-and-layer).

### E2E paths (tiered)

End-to-end paths cross Dev-Host, Docker, SSH to a gateway, USB MCUs, optional I2C, and (separately) gateway-native binaries. Use this table for **sign-off scope** and pointers to scripts/Make targets. (Tiers are a **priority guide**, not strict dependencies—for example Tier6 can run without Tier5.)

| Tier | Role | Primary entry | When to run |
|------|------|---------------|-------------|
| 0 | Offline / no hardware | `make validate` → `tests/` pytest **`-m "not hardware"`**; [tests/test_ssh_key_sharing_e2e.py](tests/test_ssh_key_sharing_e2e.py); [lab/tests/test_pico_gateway_env.py](lab/tests/test_pico_gateway_env.py), [lab/tests/test_uno_gateway_env.py](lab/tests/test_uno_gateway_env.py) | Every PR |
| 1 | CI Docker toolchains | [.github/workflows/cede-smoke.yml](.github/workflows/cede-smoke.yml) (`make -C lab/docker …`, `pytest lab/tests/`) | Every PR (workflow) |
| 2 | Live lab inner loop | **`make hw-smoke`** — Docker **hello_lab** rebuild + gateway + flash/attest ([tools/hw_smoke.sh](tools/hw_smoke.sh)) | Before merge when bench available |
| 3 | Unique digest bench | `make pi-gateway-hello-lab-hardware-smoke` (or `-pico` / `-uno`); pytest [tests/test_hello_lab_hardware_full.py](tests/test_hello_lab_hardware_full.py) etc. with `CEDE_RUN_HARDWARE_*=1` | Nightly / release bench |
| 4 | Staged pipeline | `make bootstrap-pipeline` (optional `ZERO_TARGET=uno`) | Release / lab bring-up |
| 5 | Gateway as **target** (native `hello_gateway`) | `make pi-gateway-build-native-hello`, `make pi-gateway-validate-gateway-native` | Release; **not** part of `hw-smoke` |
| 5b | **Tri-target** deploy + banners (Pi + Pico + Uno) | `make validation-targets` | When the full bench is present; proves the same environment can deploy and attest on every target type |
| 6 | I2C matrix (lab-driven) | `make pi-gateway-validate-i2c-from-lab` and aliases | After wiring + Tier2/3 green |
| 7 | Multi-app (`lab_stack`) | `make pi-gateway-flash-test-pico-lab-stack` / Uno variants | Optional application E2E |

Runbooks: [lab/docs/staged-bootstrap.md](lab/docs/staged-bootstrap.md), [docs/USER_GUIDE.md](docs/USER_GUIDE.md) §2, [docs/DEV_OP.md](docs/DEV_OP.md) Part 3, [lab/pi/docs/pico-uno-subtargets.md](lab/pi/docs/pico-uno-subtargets.md).

### Documented commands (golden manifest)

Promoted commands from [README.md](README.md) and [lab/docs/staged-bootstrap.md](lab/docs/staged-bootstrap.md) live in [config/doc_command_golden.yaml](config/doc_command_golden.yaml), tagged `kind: env`, `kind: artifact`, or `kind: hw`. [tests/test_doc_command_manifest.py](tests/test_doc_command_manifest.py) checks `make -n` for those targets, light shell snippets (`uv`, `cede --help`), and that [`.github/workflows/cede-smoke.yml`](.github/workflows/cede-smoke.yml) still matches `cede_smoke_make_lines` in the YAML. If you edit the workflow’s `make` lines, update the golden file in the same commit.

### Hardware-Gated Tests

Some tests need physical hardware (Pi, Pico, Uno). These use pytest markers and environment variables:

- `@pytest.mark.hardware` -- needs attached MCUs
- `@pytest.mark.pico` / `@pytest.mark.uno` -- specific target
- `@pytest.mark.pi_gateway` -- must run on the Pi itself

Set `CEDE_RUN_HARDWARE_FULL=1`, `CEDE_RUN_HARDWARE_PICO=1`, or `CEDE_RUN_HARDWARE_UNO=1` to enable them. Without these variables, hardware tests are skipped automatically.

Digest smokes (Tier3) live under **`tests/`** only: [tests/test_hello_lab_hardware_full.py](tests/test_hello_lab_hardware_full.py), [tests/test_hello_lab_hardware_pico_digest.py](tests/test_hello_lab_hardware_pico_digest.py), [tests/test_hello_lab_hardware_uno_digest.py](tests/test_hello_lab_hardware_uno_digest.py). Run them with **`make validate-target`** (or `uv run pytest -q tests/ -m hardware`) after exporting the matching **`CEDE_RUN_HARDWARE_*=1`**; they are **not** part of **`make validate`**.

## Code Style

### Python

- Use `from __future__ import annotations` at the top of every module.
- Add type hints to all function signatures.
- Include a module-level docstring describing the file's purpose.
- Exit with `SystemExit` and a descriptive message, not bare exceptions.

### C / Arduino

- Keep firmware focused and well-commented at the top of each file.
- Use `cede_build_id.h` (generated) for build identity -- don't edit it by hand.

### General

- No TODO/FIXME/HACK comments in committed code -- open an issue instead.
- Makefile targets should appear in `make help` output.

## Submitting Changes

1. Fork the repository and create a feature branch.
2. Make your changes and ensure `make validate` passes.
3. If you touched Docker images, run `make -C lab/docker smoke`.
4. Open a pull request with a clear description of what changed and why.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
