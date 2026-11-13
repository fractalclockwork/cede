# CEDE User Guide

A practical guide to using the Containerized Embedded Development Environment.
Covers environment validation, creating new applications, and deploying firmware to target MCUs.

**Prerequisites:** Git, Docker, and [uv](https://docs.astral.sh/uv/) installed on your Dev-Host (workstation, NUC, or VM).

**Terms:** See [Design specification — Appendix A (Glossary)](DESIGN_SPECIFICATION.md#appendix-a-glossary-reader-expansion) for CEDE and embedded vocabulary (Dev-Host, Gateway, artifact, digest sidecar, attestation, …).

---

## Table of Contents

0. [Glossary — CEDE & embedded terms](DESIGN_SPECIFICATION.md#appendix-a-glossary-reader-expansion)
1. [Getting Started](#1-getting-started)
2. [Validating the Environment](#2-validating-the-environment) — incl. [§2.0 Quick smoke test](#20-quick-smoke-test-recommended-after-every-refactor), [§2.1 Validation by target and layer](#21-validation-by-target-and-layer)
3. [Creating a New Application](#3-creating-a-new-application)
4. [Building Firmware](#4-building-firmware)
5. [Deploying to a Target MCU](#5-deploying-to-a-target-mcu)
6. [Validating a Deployment](#6-validating-a-deployment)
7. [Full Workflow: Build, Deploy, Validate](#7-full-workflow-build-deploy-validate)
8. [Debugging](#8-debugging)
9. [Lab Configuration Reference](#9-lab-configuration-reference)
10. [Make Targets Quick Reference](#10-make-targets-quick-reference)

---

## 1. Getting Started

### 1.1 Clone and Install

```bash
git clone <repo-url> && cd cede
uv sync                     # creates .venv, installs Python deps from uv.lock
```

`uv sync` installs the `cede` CLI as a console script. Verify it's available:

```bash
uv run cede --help
```

### 1.2 Understand the Architecture

CEDE uses a three-tier architecture:

| Tier | Role | Example |
|------|------|---------|
| **Dev-Host** | Code editing, Docker toolchain builds, Git, CI | Your workstation or VM |
| **Gateway** | Persistent USB/serial anchor, flashing MCUs | Raspberry Pi (SSH from Dev-Host) |
| **Target MCU** | Runs firmware | Raspberry Pi Pico W, Arduino Uno |

The Dev-Host builds firmware in Docker containers and deploys it either through the
Raspberry Pi gateway (over SSH) or directly to a USB-attached MCU.

### 1.3 Repository Layout

```
pyproject.toml              # Python package definition (cede CLI)
Makefile                    # Orchestration targets
src/cede/                   # cede CLI source (build, deploy, validate, etc.)
target-types/               # Target Type manifests (pico.yaml, uno.yaml)
config/                     # Lab config schemas and examples
  lab.example.yaml          #   Copy to lab.yaml for your lab
  lab.v2.example.yaml       #   v2 format (simplified)
docker/                     # Docker toolchain images
  Makefile                  #   Docker build/smoke/compile targets
gateway/                    # Gateway-side scripts (Pi)
templates/                  # Scaffolding templates for cede new-app
  pico/                     #   Pico project template
  uno/                      #   Uno project template
validation-apps/            # Environment-validation firmware
  hello_lab/pico/           #   Pico validation app
  hello_lab/uno/            #   Uno validation app
demo-apps/                  # Example user applications
tests/                      # pytest suite (`make validate` = -m "not hardware"; `make validate-target` = hardware)
docs/                       # Architecture and reference documentation
```

---

## 2. Validating the Environment

Validation is layered: start offline (no hardware needed), then add Docker, then the
gateway, then the MCUs. Each layer can be validated independently.

### 2.0 Quick smoke test (recommended after every refactor)

Live-hardware smoke that **rebuilds `hello_lab` (Pico + Uno) in Docker** with the current **`CEDE_IMAGE_ID`** (default: `git rev-parse --short=12 HEAD`), then exercises the gateway and **flashes** each MCU so the serial **digest=** matches that build. Run:

```bash
make hw-smoke
```

The smoke runs **eleven** checks in order: `docker version`, `cede --help`, **Docker `pico-build` + `uno-build`**, gateway health, Pico/Uno port resolution, two I2C register reads (`0x42`, `0x43`), Pico **flash + validate**, SSH **quote-probe** on the freshly flashed Pico, then Uno **flash + validate**. Each check prints `PASS` or `FAIL` with elapsed seconds; on any failure the offending log path is preserved and printed.

**Prereqs:**

- **Docker** and **uv** on the Dev-Host (the script calls `docker version` and `uv run cede --help` before building).
- **Pi gateway** reachable at **`GATEWAY`** (default `pi@cede-pi.local`). If `gateway/scripts/` or `lab/pi/` changed since the last session, run `make sync-pi-gateway-flash-deps` once to push the sparse tree (flash steps use **`SKIP_SYNC=1`** to keep the loop tight once deps are current).
- **I2C wiring** in place and Pi bus pinned to 100 kHz (see §2.6).

**Timeouts:** Docker build is capped by **`CEDE_HW_SMOKE_BUILD_TIMEOUT`** (default **900** s). Flash steps use **`CEDE_HW_SMOKE_FLASH_TIMEOUT`** (default **70** s). Override if your machine or hub is slow.

The `pico-flash-test` step is wrapped in a small retry-with-backoff (default
2 attempts, 5s between) because the Pico flash path is a USB state machine
(BOOTSEL → mass-storage → UF2 → re-enumerate as CDC) that occasionally drops
a step on Pi USB hubs. A `RETRY 1/2` line followed by a `PASS` is normal and
healthy. Tune via `CEDE_HW_SMOKE_PICO_FLASH_RETRIES` and
`CEDE_HW_SMOKE_PICO_FLASH_BACKOFF` if needed.

`hw-smoke` is the inner-loop tool. It exercises the **Raspberry Pi as SSH gateway** and **Pico/Uno as USB targets**, including a **fresh Docker rebuild** of **`hello_lab`** and **flash + serial attestation** for each MCU; it does **not** build or run the gateway-native **`hello_gateway`** binary (Tier5 in [CONTRIBUTING — E2E paths](../CONTRIBUTING.md#e2e-paths-tiered)). To prove **all three target types** in one pass—cross-build and **`scp`** **`hello_gateway`** to the Pi (stdout banner), then flash **`hello_lab`** to Pico and Uno and read each USB serial banner with the same **`digest=`**—run **`make validation-targets`** on a bench (Docker + **`GATEWAY`**). For a deep regression sweep (multi-app banners, scaffold cycle, negative tests, gateway-native, …) run the full plan in [Developer / lab operations — Part 3](DEV_OP.md#part-3--hardware-validation).

### 2.1 Validation by target and layer

**Terminology (the word “validate” is overloaded)**

- **`make validate`** — On the Dev-Host: `uv sync` then `pytest -q tests/ -m "not hardware"` (schema, CLI, transport, cloud-init, and similar). Does **not** collect `@pytest.mark.hardware` tests.
- **`make validate-target`** — Same repo tree: `pytest -q tests/ -m hardware`. Hardware digest tests **skip** unless you set **`CEDE_RUN_HARDWARE_FULL`**, **`CEDE_RUN_HARDWARE_PICO`**, or **`CEDE_RUN_HARDWARE_UNO`**; when set, they drive **`make pi-gateway-hello-lab-hardware-smoke-*`** and assert **`digest-banner:`** in captured output (**serial** attestation, not reading digest sidecar files from disk).
- **`make validation-targets`** — Bench-only Make recipe: one aligned **`FIRMWARE_DIGEST`** / **`DIGEST`**, Docker **`pico-build`** / **`uno-build`**, **`pi-gateway-build-test-gateway-native`**, then **`pi-gateway-flash-test-pico`** and **`pi-gateway-flash-test-uno`** (see root [Makefile](../Makefile)).
- **`cede validate`**, **`cede flash-test`**, **`cede run`** — CLI on the same build / deploy / serial-banner contract. Set **`CEDE_USE_CLI=1`** to route some **`make cede-*`** wrappers through the CLI.
- **`make pi-gateway-*`** — Dev-Host → SSH → Pi: sync **`lab/pi`** helpers, flash UF2/HEX, run **`pi_validate_*_serial.py`** (or gateway-native validator) on the gateway.

**Pi in two roles:** as **gateway** (SSH endpoint, USB host to MCUs) and as **native target** (**`hello_gateway`** aarch64 ELF executed on the Pi; stdout banner). **`make hw-smoke`** exercises the first plus Pico/Uno (including **Docker rebuild** of **`hello_lab`**); it does **not** run **`hello_gateway`**.

**How to validate each layer (quick reference)**

| Layer / target | What you are proving | Primary commands | Notes |
|----------------|----------------------|------------------|--------|
| **Dev-Host** (contracts) | Tooling + repo contracts without attached hardware | `make validate` | Suite is [tests/](../tests/) with **`-m "not hardware"`**. PR CI also runs **`pytest lab/tests/`** inside Docker ([cede-smoke.yml](../.github/workflows/cede-smoke.yml)); see [lab/tests/](../lab/tests/). §2.2 |
| **Docker toolchains** (no USB MCUs) | Images and **hello_lab** compile artifacts | `make -C lab/docker smoke`, **`pico-build`** / **`uno-build`**; **`make container-test-baseline`** | §2.3 |
| **Pi as gateway** | SSH reachability + USB topology for flash/serial | **`make pi-gateway-health`**, **`make bootstrap-stage-gateway`**, **`make hw-smoke`** | §2.4 |
| **Pi as native target** | Cross-built **`hello_gateway`** deployed to Pi; stdout **`digest=`** | **`make pi-gateway-build-test-gateway-native`** (or build + **`make pi-gateway-validate-gateway-native`**) | [CONTRIBUTING — E2E tier 5](../CONTRIBUTING.md#e2e-paths-tiered); not part of **`hw-smoke`**. |
| **Pico** (MCU) | UF2 flash path + USB CDC banner + **`digest=`** | **`make pi-gateway-flash-test-pico`**, **`make pi-gateway-validate-pico`** | Offline: **`uv run pytest -q lab/tests/test_pico_gateway_env.py`**. Bench pytest: **`CEDE_RUN_HARDWARE_PICO=1 make validate-target`** → [test_hello_lab_hardware_pico_digest.py](../tests/test_hello_lab_hardware_pico_digest.py). §2.5 |
| **Uno** (MCU) | HEX flash path + serial banner + **`digest=`** | **`make pi-gateway-flash-test-uno`**, **`make pi-gateway-validate-uno`** | Offline: **`uv run pytest -q lab/tests/test_uno_gateway_env.py`**. Bench pytest: **`CEDE_RUN_HARDWARE_UNO=1 make validate-target`** → [test_hello_lab_hardware_uno_digest.py](../tests/test_hello_lab_hardware_uno_digest.py). §2.5 |
| **Pi + Pico + Uno** (one digest) | Same build identity attested on all three | **`make validation-targets`** | [CONTRIBUTING — E2E tier 5b](../CONTRIBUTING.md#e2e-paths-tiered). |
| **I2C / lab matrix** | Pi as I2C master vs **`lab.yaml`** pairs | **`make pi-gateway-validate-i2c-from-lab`** | §2.6; ordered steps in [lab/docs/staged-bootstrap.md](../lab/docs/staged-bootstrap.md) §4. |

**Serial attestation vs digest sidecar**

**`make pi-gateway-flash-test-*`**, **`make validation-targets`**, and the hardware digest tests behind **`make validate-target`** check **running** firmware by reading **USB serial** (validators report **`digest-banner:`** when the banner’s **`digest=`** matches the expected build identity). A **digest sidecar** (e.g. **`.uf2.digest`** beside an artifact) is written/consumed on the **`cede deploy`** path and in CLI-focused tests such as [tests/test_cli_build.py](../tests/test_cli_build.py); those files are **not** what the digest smokes read when they call **`make pi-gateway-hello-lab-hardware-smoke-*`**.

### 2.2 Offline Python Tests (No Docker, No Hardware)

Run **environment** validation (default PR gate):

```bash
make validate
```

This runs `uv sync` followed by `pytest -q tests/ -m "not hardware"` (Dev-Host / container contracts: schema, cloud-init, CLI, transport, attestation logic, and similar). It **does not** collect `@pytest.mark.hardware` tests (digest smokes / matrix stubs).

For **hardware-marked** pytest on a bench, set the appropriate **`CEDE_RUN_HARDWARE_*`** variable and run:

```bash
make validate-target
```

To run specific subsets:

```bash
make test-config-local      # config schema only
make pi-test-cloud-init     # cloud-init render (hostname in user-data)
```

Or run pytest directly for finer control:

```bash
uv run pytest tests/test_cli_build.py -v        # build CLI tests
uv run pytest tests/test_transport.py -v         # transport tests
uv run pytest tests/ -k "attestation" -v         # attestation tests
```

**Expected result:** All tests pass. Any failure here indicates a broken development
environment and should be fixed before proceeding.

### 2.3 Docker Toolchain Validation

Build the Docker toolchain images and verify they contain the expected compilers:

```bash
make -C lab/docker build-images     # build pico-dev, arduino-dev, orchestration-dev
make -C lab/docker smoke            # toolchain smoke checks
```

The smoke test verifies:

- `pico-dev`: arm-none-eabi-gcc, cmake, ninja, picotool
- `arduino-dev`: avr-gcc, avrdude, arduino-cli
- `orchestration-dev`: Python (serial, yaml, jsonschema, pytest), cc

To validate firmware compilation without any hardware:

```bash
make -C lab/docker pico-build       # builds hello_lab → UF2
make -C lab/docker uno-build        # builds hello_lab → HEX
```

Or use the full baseline check (the same flow CI runs):

```bash
make container-test-baseline        # build images + smoke + compile + in-container pytest
```

> **Known divergence:** 3 host-only subprocess-based tests
> (`test_cli_build.py::test_generate_from_git`,
> `test_firmware_digest.py::test_make_print_firmware_digest_digest_override`, and
> `test_pi_cloud_init_render.py::test_rendered_user_data_*`) currently fail inside
> `orchestration-dev` because they shell out to `git`/`make`/`uv` with host
> assumptions. They pass cleanly on the host. The remaining 203 tests pass
> in-container.

### 2.4 Gateway Validation (Requires Raspberry Pi)

Ensure your gateway Pi is set up and reachable over SSH. Configure your lab by
copying the example config:

```bash
cp config/lab.example.yaml config/lab.yaml
# Edit config/lab.yaml: set hosts.pi.ssh_host to your Pi's hostname/IP
```

Another workstation uses the same gateway by following [lab/pi/docs/ssh-keys-bootstrap.md](../lab/pi/docs/ssh-keys-bootstrap.md) (“Adding another Dev-Host”).

Then verify connectivity:

```bash
make pi-gateway-health              # SSH health check
make pi-gateway-subtarget-check     # verify Pico/Uno USB devices are visible
make pi-gateway-print-serial        # show detected serial ports
```

### 2.5 Target MCU Validation (Requires Hardware)

Flash the built-in `hello_lab` validation firmware and check the serial banner:

**Pico:**
```bash
make -C lab/docker pico-build                  # build UF2 in Docker
make pi-gateway-flash-test-pico                # flash + validate serial banner
```

Expected serial output: `CEDE hello_lab rp2 ok digest=<git-sha>`

**Uno:**
```bash
make -C lab/docker uno-build                   # build HEX in Docker
make pi-gateway-flash-test-uno                 # flash + validate serial banner
```

Expected serial output: `CEDE hello_lab ok digest=<git-sha>`

### 2.6 I2C Bus Validation (Optional)

If your lab has I2C wiring between the Pi and MCUs:

```bash
make pi-gateway-diagnose-i2c                   # i2cdetect scan
make pi-gateway-validate-i2c-from-lab          # validate all enabled I2C pairs
```

> **Hardware caveat:** `pi-gateway-validate-i2c-from-lab` performs Pi→Uno and
> Pi→Pico register reads which require a clean I2C signal at the configured
> bus speed. If your level shifter cannot drive the 400 kHz default cleanly,
> these reads return garbage (`expected reg[0] == 0xce, got …`). Drop the Pi
> bus speed in `/boot/firmware/config.txt`
> (`dtparam=i2c_arm=on,i2c_arm_baudrate=100000`) or replace the level shifter.

### 2.7 Full Staged Bootstrap

Run the complete bring-up sequence in order:

```bash
make bootstrap-stage-dev-host       # offline: config tests + Docker builds
make bootstrap-stage-gateway        # SSH health + subtarget check
make bootstrap-pipeline             # flash + validate both MCUs + I2C
```

Or the all-in-one developer readiness check:

```bash
make cede-dev-preflight             # dev-host + gateway stages
```

---

## 3. Creating a New Application

The `cede new-app` command scaffolds a complete project from templates.

### 3.1 Scaffold a Pico Application

```bash
uv run cede new-app my_sensor --target pico
```

This creates:

```
demo-apps/my_sensor/pico/
  CMakeLists.txt            # CMake project (Pico SDK)
  cede_app.yaml             # Application manifest
  src/
    main.c                  # Entry point with banner + digest
```

### 3.2 Scaffold an Uno Application

```bash
uv run cede new-app my_sensor --target uno
```

This creates:

```
demo-apps/my_sensor/uno/
  app.ino                   # Arduino sketch (renamed automatically at build time)
  cede_app.yaml             # Application manifest
  cede_build_id.h           # Build identity header (placeholder; regenerated at build time)
```

**Note (Arduino convention):** `arduino-cli` expects the `.ino` filename to match
its parent directory name. `cede build` handles this automatically by staging the
sketch into a temporary directory whose name matches the `.ino` file. The resulting
artifact is named after the `.ino` file, e.g. `build/app.ino.hex` for the scaffolded
template. Update `entrypoint` in `cede_app.yaml` to match the produced filename, or
rename `app.ino` to `<application_id>.ino` before the first build.

### 3.3 Output Directory and Category Options

By default, applications are created under `demo-apps/`. Override with `--output-dir`:

```bash
uv run cede new-app my_test -t pico --output-dir validation-apps
```

Set the category for organizational purposes:

```bash
uv run cede new-app my_test -t pico --category validation
```

Categories: `user` (default), `validation`, `gateway`.

### 3.4 Application Manifest (cede_app.yaml)

Every application includes a `cede_app.yaml` that declares:

```yaml
application_id: "my_sensor"
target: pico
category: user
entrypoint: "build/my_sensor.uf2"
resources:
  usb_serial:
    banner_prefix: "CEDE my_sensor rp2 ok"
```

Key fields:

| Field | Purpose |
|-------|---------|
| `application_id` | Unique name; appears in the serial banner |
| `target` | Target type (must match a `target-types/*.yaml`) |
| `category` | `user`, `validation`, or `gateway` |
| `entrypoint` | Path to the build artifact (relative to app dir) |
| `resources.usb_serial.banner_prefix` | Expected prefix in the serial attestation banner |

### 3.5 Edit the Generated Code

**Pico (C/C++):** Edit `src/main.c`. The template provides:

- `stdio_init_all()` for USB serial
- The CEDE attestation banner (printed at boot)
- A main loop you can fill with your sensor logic

**Uno (Arduino):** Edit `app.ino` (rename to match the parent directory before
building -- see the Arduino convention note in section 3.2). The template provides:

- `Serial.begin(115200)` for USB serial
- The CEDE attestation banner (printed in `setup()`)
- A `loop()` you can fill with your logic

The attestation banner (`CEDE <app_name> ... ok digest=<sha>`) must be the first line
printed. CEDE's validation step looks for this to confirm the correct firmware is running.

**Scaffold caveats (validation contract):** the templates emit the banner once at
boot and define `CEDE_IMAGE_ID` as `"unknown"` if not overridden. To make
`cede validate` pass against a fresh scaffold, either (a) re-print the banner in
the main loop on a slow cadence so it's always visible when `cede validate` reads
the port, and (b) wire `CEDE_IMAGE_ID` into the build:

- **Pico:** add `target_compile_definitions(my_sensor PRIVATE CEDE_IMAGE_ID="$ENV{CEDE_IMAGE_ID}")`
  to `CMakeLists.txt` and ensure `CEDE_IMAGE_ID` is exported in the build environment
  (`cede build` does this from the resolved Build Identity).
- **Uno:** add `bash tools/gen_cede_image_id.sh` (or equivalent) to regenerate
  `cede_build_id.h` before each compile, matching the pattern in `lab/uno/hello_lab/`.

---

## 4. Building Firmware

### 4.1 Using the cede CLI

Build with the `cede build` command, pointing at your application directory:

```bash
uv run cede build --target pico --app-dir demo-apps/my_sensor/pico
```

This:

1. Loads the target type definition from `target-types/pico.yaml`
2. Generates a Build Identity from the current git SHA
3. Runs the Docker toolchain (`cede/pico-dev:local`) with the build command
4. Produces the artifact (e.g., `build/my_sensor.uf2`)
5. Writes a `.cede-digest` sidecar file for attestation

For Uno:

```bash
uv run cede build --target uno --app-dir demo-apps/my_sensor/uno
```

### 4.2 Using Docker Directly

The Docker Makefile builds the legacy lab apps under `lab/pico/` and `lab/uno/`
(used for `hello_lab` and `lab_stack` validation firmware). Select the app with
`PICO_APP` or `UNO_APP`:

```bash
make -C lab/docker pico-build PICO_APP=hello_lab     # → lab/pico/hello_lab/build/hello_lab.uf2
make -C lab/docker uno-build  UNO_APP=lab_stack      # → lab/uno/lab_stack/build/lab_stack.ino.hex
```

For applications scaffolded under `demo-apps/`, use `cede build` (Section 4.1)
instead — it loads the toolchain image and build command from the target type
manifest.

### 4.3 Build Identity

Every build embeds a 12-character identity token derived from the git commit SHA.
This token appears in the serial banner as `digest=<token>` and is used by the
validation step to confirm the correct firmware version is running on the MCU.

Override the identity with:

```bash
uv run cede build -t pico --app-dir demo-apps/my_sensor/pico --digest my_custom_id
```

---

## 5. Deploying to a Target MCU

### 5.1 Deployment Modes

CEDE supports two deployment modes:

| Mode | Path | When to Use |
|------|------|-------------|
| **Gateway** | Dev-Host → SSH → Pi → USB → MCU | MCU plugged into Pi (remote lab) |
| **Direct** | Dev-Host → USB → MCU | MCU plugged directly into Dev-Host |

The mode is auto-detected from `lab.yaml` (the `attach` field on each target).
Override explicitly with `--mode gateway` or `--mode direct`.

### 5.2 Deploy via the cede CLI

Pass the artifact explicitly (recommended):

```bash
uv run cede deploy --target pico --artifact demo-apps/my_sensor/pico/build/my_sensor.uf2
```

Or `cd` into the application directory and let CEDE find the build output
(it searches `./build/` matching the target's artifact pattern):

```bash
cd demo-apps/my_sensor/pico && uv run cede deploy --target pico
```

For Uno (note: the scaffolded sketch produces `build/app.ino.hex` because the
template's source file is `app.ino`):

```bash
uv run cede deploy --target uno --artifact demo-apps/my_sensor/uno/build/app.ino.hex
```

### 5.3 Deploy via Make Targets

**Gateway mode (existing bash scripts):**

```bash
# Pico: flash via Pi gateway (UF2 path must be absolute or relative to repo root)
make pi-gateway-flash-pico UF2="$PWD/demo-apps/my_sensor/pico/build/my_sensor.uf2"

# Uno: flash via Pi gateway
make pi-gateway-flash-uno HEX="$PWD/demo-apps/my_sensor/uno/build/app.ino.hex"
```

**CLI mode (set CEDE_USE_CLI=1):**

```bash
CEDE_USE_CLI=1 make cede-deploy-pico CEDE_ARTIFACT=demo-apps/my_sensor/pico/build/my_sensor.uf2
```

### 5.4 What Happens During Deploy

**Pico deploy sequence:**

1. Transport copies the `.uf2` artifact to the gateway (or local `/tmp`)
2. `picotool reboot -uf` puts the Pico into BOOTSEL mode (pre-flash command)
3. `picotool load -f -v -x <artifact>` flashes and verifies the firmware
4. 3-second post-flash delay for the MCU to reboot and enumerate USB serial

**Uno deploy sequence:**

1. Transport copies the `.hex` artifact to the gateway (or local `/tmp`)
2. `avrdude -p atmega328p -c arduino -P <port> -b 115200 -D -U flash:w:<artifact>:i` programs the flash
3. 2-second post-flash delay for the MCU to reset

---

## 6. Validating a Deployment

### 6.1 Serial Banner Attestation

After flashing, CEDE reads the target's USB serial port and checks for the
attestation banner. The banner format is:

```
CEDE <app_id> [<mcu_suffix>] ok digest=<build_identity>
```

Examples:

- Pico: `CEDE my_sensor rp2 ok digest=aec771d88ba3`
- Uno: `CEDE my_sensor ok digest=aec771d88ba3`

### 6.2 Validate via the cede CLI

```bash
uv run cede validate --target pico
```

This:

1. Resolves the serial port (from `target-types/pico.yaml` device matching rules)
2. Reads serial output at 115200 baud
3. Checks the banner prefix matches the expected application
4. Compares the `digest=` token against the current git SHA (or a `--digest` override)

```bash
uv run cede validate --target pico --digest aec771d88ba3
uv run cede validate --target uno --port /dev/ttyACM0
```

### 6.3 Validate via Make Targets

```bash
make pi-gateway-validate-pico
make pi-gateway-validate-uno
```

### 6.4 Validation Failures

Common failure modes and resolutions:

| Symptom | Cause | Fix |
|---------|-------|-----|
| No serial output | MCU not enumerated, wrong port | Check USB cable, run `pi-gateway-print-serial` |
| Banner prefix mismatch | Wrong firmware flashed | Re-flash the correct artifact |
| Digest mismatch | Stale firmware from an older build | Rebuild and re-flash |
| Timeout | MCU crashed or banner delay too short | Increase `post_flash_delay_s` in target type |

---

## 7. Full Workflow: Build, Deploy, Validate

### 7.1 One-Command Cycle

The `cede run` command chains build, deploy, and validate:

```bash
uv run cede run --target pico --app-dir demo-apps/my_sensor/pico
```

This is equivalent to running:

```bash
uv run cede build   -t pico --app-dir demo-apps/my_sensor/pico
uv run cede deploy  -t pico
uv run cede validate -t pico
```

### 7.2 Flash-Test (Deploy + Validate)

If you've already built and just want to re-flash and verify:

```bash
uv run cede flash-test --target pico --artifact demo-apps/my_sensor/pico/build/my_sensor.uf2
```

The Uno equivalent uses `build/app.ino.hex` from the scaffolded template:

```bash
uv run cede flash-test --target uno --artifact demo-apps/my_sensor/uno/build/app.ino.hex
```

Or from inside the app directory (auto-detects `./build/*.uf2` or `./build/*.hex`):

```bash
cd demo-apps/my_sensor/pico && uv run cede flash-test --target pico
```

### 7.3 Make-Based Flash-Test

```bash
make pi-gateway-flash-test-pico UF2="$PWD/demo-apps/my_sensor/pico/build/my_sensor.uf2"
make pi-gateway-flash-test-uno  HEX="$PWD/demo-apps/my_sensor/uno/build/app.ino.hex"
```

### 7.4 Iterative Development Workflow

A typical edit-build-flash-validate cycle:

```bash
# 1. Edit your application code
vim demo-apps/my_sensor/pico/src/main.c

# 2. Build + deploy + validate in one step
uv run cede run -t pico --app-dir demo-apps/my_sensor/pico

# 3. If something fails, debug via serial console
uv run cede debug -t pico --method serial
```

---

## 8. Debugging

### 8.1 Serial Console

Open an interactive serial console to the target:

```bash
uv run cede debug --target pico --method serial
```

This launches `picocom` (or `minicom` as fallback) at 115200 baud on the
auto-detected serial port. Exit with `Ctrl+A, Ctrl+X`.

Log serial output to a file:

```bash
uv run cede debug -t pico --method serial --log output.log
```

Override the port:

```bash
uv run cede debug -t uno --method serial --port /dev/ttyACM0
```

### 8.2 GDB Debugging (Pico)

For Pico targets with SWD debug probes:

```bash
uv run cede debug --target pico --method gdb --elf build/my_sensor.elf
```

This starts an OpenOCD + GDB session using the debug configuration from
`target-types/pico.yaml`.

### 8.3 Port Resolution

CEDE auto-detects serial ports using the matching rules in the target type manifest:

- **Primary:** `/dev/serial/by-id/usb-Raspberry_Pi_*` (Pico) or `usb-Arduino_*` (Uno)
- **Fallback:** `/dev/ttyACM*`, `/dev/ttyUSB*`

On the gateway, the `discover_serial.py` script handles multi-device disambiguation.

---

## 9. Lab Configuration Reference

### 9.1 Creating lab.yaml

Copy the example and customize for your lab:

```bash
cp config/lab.example.yaml config/lab.yaml
```

The file is gitignored -- it contains machine-specific details.

Another workstation uses the same gateway by following [lab/pi/docs/ssh-keys-bootstrap.md](../lab/pi/docs/ssh-keys-bootstrap.md) (“Adding another Dev-Host”).

### 9.2 Key Configuration Sections

**Gateway (v2 format):**

```yaml
schema_version: 2

gateway:
  ssh_host: cede-pi.local       # hostname or IP of your Pi
  ssh_user: pi                  # SSH user
  work_dir: "~/cede"            # sparse sync directory on the Pi
```

**Targets:**

```yaml
targets:
  pico:
    type: pico                  # references target-types/pico.yaml
    attach: gateway             # "gateway" or "direct"
    serial:
      by_id_glob: "/dev/serial/by-id/usb-Raspberry_Pi_*"
      fallback_globs:
        - "/dev/ttyACM*"

  uno:
    type: uno
    attach: gateway
    serial:
      by_id_glob: "/dev/serial/by-id/usb-Arduino_*"
      fallback_globs:
        - "/dev/ttyUSB*"
        - "/dev/ttyACM*"
```

### 9.3 Target Type Manifests

Each supported MCU family is defined in `target-types/<name>.yaml`. These declare:

- **Toolchain:** Docker image, build command, artifact pattern
- **Flash:** Tool, command template, pre/post-flash commands and delays
- **Serial:** Baud rate, banner pattern, device matching rules
- **Debug:** Method (SWD, none), tool, GDB port

Example (`target-types/pico.yaml`):

```yaml
target_type: pico
display_name: "Raspberry Pi Pico / Pico W (RP2040)"

toolchain:
  image: cede/pico-dev:local
  build_command: "cmake -B build -G Ninja && ninja -C build"
  artifact_pattern: "build/*.uf2"

flash:
  tool: picotool
  command: "picotool load -f -v -x {artifact}"
  pre_flash: "picotool reboot -uf"
  post_flash_delay_s: 3

serial:
  speed: 115200
  banner_pattern: "CEDE .+ ok digest={digest}"
  device_match:
    by_id_glob: "/dev/serial/by-id/usb-Raspberry_Pi_*"
    fallback_globs:
      - "/dev/ttyACM*"
```

### 9.4 Environment Variable Overrides

| Variable | Purpose | Example |
|----------|---------|---------|
| `CEDE_LAB_CONFIG` | Path to lab.yaml (overrides default search) | `CEDE_LAB_CONFIG=~/my-lab.yaml` |
| `CEDE_USE_CLI` | Enable CLI delegation in Makefile targets | `CEDE_USE_CLI=1` |
| `CEDE_ARTIFACT` | Explicit artifact path for deploy/flash-test | `CEDE_ARTIFACT=build/app.uf2` |
| `GATEWAY` | SSH address for Make gateway targets | `GATEWAY=pi@10.0.0.5` |
| `DIGEST` | Override build identity in Make targets | `DIGEST=custom123` |
| `CEDE_IMAGE_ID` | Override build identity in Docker builds | `CEDE_IMAGE_ID=abc123` |

---

## 10. Make Targets Quick Reference

### Offline / Dev-Host

| Target | Description |
|--------|-------------|
| `make sync` | Install Python deps via uv |
| `make validate` | Offline pytest on `tests/` (`-m "not hardware"`) |
| `make validate-target` | Pytest `-m hardware` on `tests/` (set `CEDE_RUN_HARDWARE_*` on a bench) |
| `make test-config-local` | Config schema tests only |
| `make pi-test-cloud-init` | Cloud-init render test |
| `make pi-bootstrap-render` | Render cloud-init files from lab.yaml |
| `make print-firmware-digest` | Show current git-derived build identity |

### Docker Toolchains

| Target | Description |
|--------|-------------|
| `make -C lab/docker build-images` | Build all Docker toolchain images |
| `make -C lab/docker smoke` | Smoke-test all toolchains |
| `make -C lab/docker pico-build` | Build Pico hello_lab (UF2) |
| `make -C lab/docker uno-build` | Build Uno hello_lab (HEX) |
| `make container-test-baseline` | Full CI baseline (build + smoke + compile + pytest) |

### Gateway

| Target | Description |
|--------|-------------|
| `make pi-gateway-health` | SSH connectivity check |
| `make pi-gateway-subtarget-check` | Verify MCU USB devices on Pi |
| `make pi-gateway-print-serial` | List serial ports on Pi |
| `make pi-gateway-resolve-port-pico` | Show detected Pico serial port |
| `make pi-gateway-resolve-port-uno` | Show detected Uno serial port |

### Flash and Validate

| Target | Description |
|--------|-------------|
| `make pi-gateway-flash-pico` | Flash Pico via gateway |
| `make pi-gateway-flash-uno` | Flash Uno via gateway |
| `make pi-gateway-validate-pico` | Validate Pico serial banner |
| `make pi-gateway-validate-uno` | Validate Uno serial banner |
| `make pi-gateway-flash-test-pico` | Flash + validate Pico |
| `make pi-gateway-flash-test-uno` | Flash + validate Uno |
| `make validation-targets` | Build aligned **`hello_lab`** + **`hello_gateway`**, deploy to Pico, Uno, and Pi, assert each attestation banner (bench; see [CONTRIBUTING — E2E](../CONTRIBUTING.md#e2e-paths-tiered) tier 5b) |

### cede CLI Targets (CEDE_USE_CLI=1)

| Target | Description |
|--------|-------------|
| `cede-build-pico` | Build Pico via CLI |
| `cede-build-uno` | Build Uno via CLI |
| `cede-deploy-pico` | Deploy to Pico via CLI |
| `cede-deploy-uno` | Deploy to Uno via CLI |
| `cede-validate-pico` | Validate Pico via CLI |
| `cede-validate-uno` | Validate Uno via CLI |
| `cede-flash-test-pico` | Deploy + validate Pico via CLI |
| `cede-flash-test-uno` | Deploy + validate Uno via CLI |
| `cede-run-pico` | Build + deploy + validate Pico |
| `cede-run-uno` | Build + deploy + validate Uno |

### Bootstrap Pipeline

| Target | Description |
|--------|-------------|
| `make bootstrap-stage-dev-host` | Config tests + Docker builds |
| `make bootstrap-stage-gateway` | SSH + subtarget checks |
| `make bootstrap-pipeline` | Full staged bring-up (both MCUs) |
| `make cede-dev-preflight` | Dev readiness (dev-host + gateway) |
