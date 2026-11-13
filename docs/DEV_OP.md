# CEDE developer & lab operations

This document **replaces** `docs/ROADMAP.md` and `docs/HARDWARE_VALIDATION.md` (merged to reduce fragmentation). Use it for **current shipping behavior**, **roadmap direction**, and the **full hardware validation checklist**.

**Normative architecture and philosophy** remain in [DESIGN_SPECIFICATION.md](DESIGN_SPECIFICATION.md) (DS-1..DS-18). **Day-to-day commands** are in [USER_GUIDE.md](USER_GUIDE.md).

**Deep references (unchanged paths):** [lab/docs/staged-bootstrap.md](../lab/docs/staged-bootstrap.md) · [lab/pi/docs/bus-wiring.md](../lab/pi/docs/bus-wiring.md) · other `lab/pi/docs/*` as linked from the checklist below.

---

## Document map

- [Part 1 — Current state](#part-1--current-state)
- [Part 2 — Roadmap](#part-2--roadmap)
- [Part 3 — Hardware validation](#part-3--hardware-validation)

### E2E test tiers (summary)

Operator-facing **tier 0–7** table (scripts, Make targets, cadence): [CONTRIBUTING.md — E2E paths (tiered)](../CONTRIBUTING.md#e2e-paths-tiered). **Inner-loop** hardware is Tier2 (`make hw-smoke`). **Gateway-native** `hello_gateway` on the Pi is Tier5 and is **not** included in `hw-smoke`; schedule it for release / Part3-style sweeps.

---

## Part 1 — Current state

### How to read this roadmap

- **Spec is authoritative.** When the roadmap and the spec disagree,
  the spec wins. Roadmap items propose work; the spec records contracts
  that the work must satisfy.
- **Phases are ordered.** Earlier phases unblock later ones. Each
  phase has a concrete *Definition of Done*.
- **Inner-loop first.** The live-hardware smoke (`make hw-smoke`,
  DS-14.2) is the tripwire for every change in this roadmap. If a
  phase regresses the smoke, that phase is not done.
- **Bug references** (`B-NN`) are the hardware validation findings
  catalogued in Part 3 (below).

### Status snapshot

| Capability | DS reference | State |
|------------|--------------|-------|
| Three-tier architecture, target-type abstraction | DS-3, DS-5 | In place; Pico + Uno are configuration-driven exemplars |
| Unified `cede` CLI (`build`/`deploy`/`validate`/`debug`/`flash-test`/`run`/`new-app`) | DS-7 | In place; some legacy Make-only paths remain |
| SSH + rsync transport with shell-quoting invariant | DS-8.1 | In place; `shlex.join` (Python) and `printf '%q '` (shell) enforced; `quote-probe` in `make hw-smoke` |
| Stable serial-by-id discovery | DS-8.3 | In place across resolvers; numbered ACM paths forbidden |
| Build identity + serial-banner attestation | DS-9 | In place for Validation Apps (`hello_lab` Pico/Uno) |
| Quick hardware smoke (`make hw-smoke`) | DS-14.2 | In place; 11 checks (incl. Docker hello_lab rebuild), bounded timeouts, retry-with-backoff on Pico flash |
| Deep hardware regression plan | DS-14.2 | In place at `DEV_OP.md#part-3--hardware-validation` |
| Scaffold validation contract | DS-9.3, DS-9.4, DS-18.5 | **Partial** -- B-18 (Uno entrypoint) and B-19 (banner loop + `CEDE_IMAGE_ID` injection) are open |
| I2C bus pinned to 100 kHz at gateway | DS-14.2 | Operational; codified in spec |
| Application separation (`validation-apps/` vs `demo-apps/` vs external) | DS-18 | Partial -- legacy `lab/` paths still hold app-shaped content during migration |

---

## Part 2 — Roadmap

### Phases

### Phase 1 -- Stabilize the inner loop

**DS:** DS-8.1 (quoting), DS-8.3 (by-id), DS-14.2 (smoke), DS-14.3 (bounded retry).

**Closes / keeps closed:** B-1, B-6, B-12, B-13, B-15, B-16, B-17, B-20.

Keep `make hw-smoke` honest:

- 11 checks (Docker rebuild of `hello_lab` + gateway + I2C + flash/validate + quote-probe); wall-clock is often **minutes** on a cold Docker cache (tune `CEDE_HW_SMOKE_BUILD_TIMEOUT`).
- `quote-probe` continues to assert the SSH-quoting invariant.
- Pico flash uses bounded retry-with-backoff; Uno stays single-shot.
- Each check is bounded by `timeout`; failed runs preserve per-step
  logs.
- Add CI hook (when CI hardware is wired) that runs `make hw-smoke`
  on every PR that touches transport, gateway scripts, target-type
  manifests, or the CLI.

**Definition of Done:** `make hw-smoke` is the documented pre-merge
gate (`USER_GUIDE.md` §2.0); a green smoke is the contract for "the
refactor did not regress the lab."

### Phase 2 -- Scaffolds become validation-ready

**DS:** DS-9.3 (build-identity injection), DS-9.4 (banner emission),
DS-18.5 (scaffold contract).

**Closes:** B-18, B-19.

Make `cede new-app` produce projects that pass build / deploy /
validate **without manual edits**:

1. **Pico template (`templates/pico-app/`)**
   - `CMakeLists.txt` consumes `CEDE_IMAGE_ID` from the environment
     and adds `-DCEDE_IMAGE_ID="..."` (default literal `"unknown"` if
     unset).
   - `src/main.c` includes the generated header and prints the Serial
     Banner on a 1 - 5 s loop, not just at boot.
2. **Uno template (`templates/uno-app/`)**
   - Either rename the template's `app.ino` to match the
     `application_id`, or fix `cede_app.yaml` `entrypoint` to follow
     the actual Arduino CLI artifact name (`build/<sketch>.ino.hex`).
   - Add a build step that injects `CEDE_IMAGE_ID` (e.g. generated
     header that the sketch `#include`s).
   - Loop the Serial Banner.
3. **Lockstep with `validation-apps/`** so the reference firmware and
   the templates do not drift.
4. **Smoke coverage:** add a phase to `DEV_OP.md#part-3--hardware-validation`
   (already present as Phase 13) that scaffolds, builds, deploys, and
   validates a fresh Pico+Uno pair, then tears it down. Aim is for
   that phase to go green, removing the "known-fail" caveats.

**Definition of Done:** scaffolding cycle in
`DEV_OP.md#part-3--hardware-validation` runs end-to-end without B-18/B-19
caveats, and `USER_GUIDE.md` §3 drops the "Scaffold caveats" notes.

### Phase 3 -- Finish the CLI-first migration

**DS:** DS-7 (unified workflow), DS-12 (mode resolution).

**Closes / consolidates:** B-3, B-4, B-5, B-7, B-8, B-9, B-10.

The `cede` CLI already covers `build / deploy / validate / debug /
flash-test / run / new-app`. The next step is to retire Make-only
legacy paths where they are not adding value:

- Audit each `make pi-gateway-*` and `make cede-*` target. For each,
  decide whether it should be (a) a thin wrapper around the CLI,
  (b) deleted, or (c) kept as a Phase-0/Phase-1 bootstrap helper
  documented as such.
- Where the CLI and Make targets disagree (e.g. argument plumbing,
  default mode selection), the CLI is the source of truth; fix the
  Make wrapper.
- Keep gradual-adoption gates (`CEDE_USE_CLI=1` and similar) only
  while at least one consumer still depends on the legacy path.
- Update `USER_GUIDE.md` to lead with `cede ...` everywhere; demote
  Make examples to "advanced / scripting" call-outs.

**Definition of Done:** `cede --help` is the canonical entry point in
`USER_GUIDE.md`; remaining Make targets either wrap CLI subcommands or
are explicitly bootstrap helpers (toolchain image build, gateway
sparse-tree sync).

### Phase 4 -- Environment / application separation

**DS:** DS-11.6 (separation principle), DS-18.4 (User Apps), DS-18.6
(repo layout, migration note).

Move the repo to the v2 layout from DS-18.6:

- Confirm `validation-apps/hello_lab/{pico,uno}` are the canonical
  validation firmware and that no application logic remains under
  `lab/` other than transitional symlinks.
- Demote `demo-apps/` (`lab_stack`, `ssd1306_dual`, `ssd1306_eyes`)
  to clearly marked demos: each gets a top-level `README.md` stating
  it is a *consumer* of CEDE, not part of CEDE.
- Document the path for graduating a demo out of the tree into its
  own repository (DS-18.4) so future demos do not accumulate in
  `demo-apps/`.
- Tests under `tests/` that depend on demo-app source (e.g. PIL-based
  SSD1306 tests) get an `--ignore` story or move with the demo.

**Definition of Done:** the v2 repo layout in DS-18.6 matches reality;
nothing under `lab/` is application-shaped except symlinks; each demo
has an explicit "this is not part of CEDE" header.

### Phase 5 -- Target-Type extensibility, demonstrated

**DS:** DS-5 (target abstraction), DS-15.1 (adding a new target type).

Prove DS-5's claim that adding an MCU family is YAML + Dockerfile,
not structural code change, by adding one new target type
end-to-end (e.g. ESP32 or STM32 with a cheap dev board):

1. New `target-types/<name>.yaml` matching the DS-5.3 contract.
2. New `docker/<name>-dev/Dockerfile` and `TOOLCHAIN_VERSIONS` entry.
3. Gateway `bootstrap.sh` adds the flash tool.
4. New `validation-apps/hello_lab/<name>/` with `cede_app.yaml`,
   build files, and source that meets DS-9.3 and DS-9.4.
5. `lab.yaml` (or `lab.example.yaml`) gains the new target.
6. `make hw-smoke` is extended (or its target list parameterized) so
   the new target is covered by the inner loop.

**Definition of Done:** the new target flows through `cede build /
deploy / validate / flash-test` without code changes outside its
manifest, Dockerfile, and validation app; DS-5 prose updated if any
gap is discovered.

### Phase 6 -- Release-grade validation, kept current

**DS:** DS-14.2 (release plan), DS-16.4 (test-gated progress).

Treat `DEV_OP.md#part-3--hardware-validation` as the definition of "ready to
release":

- Run it before any tag.
- Each new bug found becomes a `B-NN` entry that points at the step
  that caught it; if no step caught it, add a step before closing the
  bug.
- Promote stable findings into spec contracts (per the Status and
  Operating Guide block at the top of `DESIGN_SPECIFICATION.md`)
  rather than letting them ossify in the validation doc.
- Cross-link each roadmap phase milestone to the
  `DEV_OP.md#part-3--hardware-validation` step that proves it.

**Definition of Done:** `DEV_OP.md#part-3--hardware-validation` is the
release gate; the roadmap, spec, and validation doc all point at each
other consistently.

### Phase 7 -- Gateway as SDL instrument host

**DS:** DS-17 (gateway instrument host / SDL physical layer), DS-18
(environment vs application separation).

**North star:** CEDE (Dev-Host + cede-gateway) is the **physical control
plane** for a self-driving lab. Experiment orchestration and policy stay
in **self-driving-lab**; device protocol, safety, and acquisition stay in
**instrument repos**. The gateway is the unified way those projects reach
and manage physical devices. Phase 7 is a **repeatable onboarding
pattern**, not a one-off gadget list — gateway services grow as new
instruments are added.

| Layer | Owns | Examples |
|-------|------|----------|
| self-driving-lab | Orchestration, policy, campaign state | SOPs, OperatorGate, adapters |
| Instrument repos | IOP / protocol / abort / idle-safe | spectrometer-lab, crt-drive, Marlin IOP, camera projects |
| CEDE Dev-Host + gateway | Toolchains, flash/sync, stable attach, discovery, access groups | by-id serial, UVC nodes, Pico flash, SSH sparse tree |

**Boundary:** CEDE does **not** absorb spectrometer protocol, Marlin
G-code, V4L capture apps, or campaign policy. It **does** document and
grow gateway services: discover, name, permission, transport, and (where
relevant) flash/monitor hooks that instrument repos consume. No new
gateway daemons in this phase (DS-1.2); services mean config contracts
and Make/SSH helpers first.

#### Instrument onboarding contract

Every new physical instrument should get the same CEDE-side checklist:

1. **Identity** — USB vendor/product or by-id glob; class (serial / CDC /
   UVC / other).
2. **lab.yaml stub** — named entry under `serial.devices` or a future
   `instruments:` section (comment-only until schema is extended).
3. **Gateway OS needs** — groups (`dialout`, `video`), udev notes,
   baud/defaults if serial.
4. **CEDE surface** — discovery list target and/or health note;
   flash/monitor only if MCU-like.
5. **External owner** — link to the instrument repo (IOP owns protocol
   and abort/idle-safe).
6. **SDL hook** — note that SDL Stage 0 inventory / Stage 1 IOP talks
   through this gateway path.
7. **Non-interference** — Hello Lab Pico/Uno resolvers must not steal
   instrument ports; document glob collisions (e.g. `usb-Arduino_*`
   matches Mega as well as Uno).

#### First-cohort inventory (cede-pi, battlestar bring-up)

| Device | USB ID | Stable path | Instrument / owner |
|--------|--------|-------------|--------------------|
| Prolific PL2303 | `067b:2303` | `/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0` → `ttyUSB0` | **LS 55** spectrum analyzer — spectrometer-lab (9600 8N1) |
| Arduino Mega 2560 | `2341:0042` | `/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_*` → `ttyACM1` | **Marlin** 3D printer — candidate; confirm with `M115` before locking local `lab.yaml` |
| Raspberry Pi Pico | `2e8a:000a` | `/dev/serial/by-id/usb-Raspberry_Pi_Pico_*` → `ttyACM0` | **crt-drive** (RP2040 CRT ASIC replacement) |
| Logitech C310 | `046d:081b` | UVC `/dev/video0` (+ `/dev/video1`) | Camera / glass HIL (crt-drive + SDL vision path) |
| HDMI | — | `card0-HDMI-A-1` | Optional digital kiosk ([lab/pi/docs/dashboard-hdmi.md](../lab/pi/docs/dashboard-hdmi.md)); **not** the analog CRT |

**Not attached yet:** Fujifilm FinePix A500 (separate camera-control
project). **Collision note:** Hello Lab `uno` by-id glob `usb-Arduino_*`
also matches Mega — instrument stubs must not be wired into Hello Lab
resolvers until they are instrument-aware.

#### Near-term work

1. Keep this inventory and owners current in this section.
2. Comment stubs in `config/lab.example.yaml` modeling the pattern
   (`ls55`, `marlin`, camera / crt-drive notes).
3. List-only discovery helpers later (`print-serial` / optional
   `print-video`) — no IOP code in CEDE.
4. crt-drive attach via gateway: reuse existing `pi-gateway-*` Pico flash
   / monitor helpers; instrument firmware stays in crt-drive.
5. Cross-link external bring-up: spectrometer-lab Quick Connect; SDL
   instrument bring-up ladder; crt-drive toolchains (today Dev-Host USB;
   migrate attach through cede-pi).

**Definition of Done:** framing + onboarding contract + first-cohort
inventory live in this phase; example lab stubs and DS-17 rows updated;
`make hw-smoke` unchanged (Hello Lab Pico/Uno only); no instrument
protocol code in CEDE.

### Non-goals (for now)

These remain parked (see DS-17) except where Phase 7 explicitly tracks
gateway **instrument hosting**:

- Multi-gateway topologies.
- OTA firmware updates.
- Sensor framework / sensor catalog (as a CEDE-owned driver stack).
- Dashboards, telemetry, MQTT as CEDE products.
- Resource locking across multiple Dev-Hosts.
- Full IOP / SOP / campaign policy inside CEDE (belongs in instrument
  repos and self-driving-lab).

**Tracked in Phase 7 (not a non-goal):** repeatable gateway onboarding
and physical attach for external instruments (LS 55, Marlin, UVC camera,
crt-drive, and future devices).

MCU Target Type extensibility (Phase 5) and release-grade validation
(Phase 6) still gate how aggressively later gateway helpers land; Phase 7
documents the SDL physical-layer direction in parallel.

---

## Part 3 — Hardware validation

The checklist below is the former **Hardware Validation Plan** (verbatim structure, headings demoted under this part). **Inner-loop:** run `make hw-smoke` first ([USER_GUIDE §2.0](USER_GUIDE.md#20-quick-smoke-test-recommended-after-every-refactor)).

### Part 3 — Mini-TOC (phases)

Jump to the same anchors as the original plan (heading text preserved for slugs where possible).


### CEDE Hardware Validation Plan

A structured, repeatable checklist an operator runs against live hardware
(Raspberry Pi gateway + Pico + Uno + I2C bus) to confirm every Make target and
`cede` CLI flow still works end-to-end. Each step has an exact command, the
exact tokens that must appear in the output, and a pointer to the historical
bug it guards against.

Run this top-to-bottom whenever:

- A change touches `Makefile`, `gateway/scripts/`, `src/cede/`, `target-types/`,
  `docker/`, or `config/`.
- A new Target Type or application is added.
- The Pi gateway is reimaged.
- Before cutting a release tag.

> **Inner-loop note:** before opening this plan, run the lightweight
> `make hw-smoke` first (rebuilds `hello_lab` in Docker, then flash + validate; see [USER_GUIDE.md §2.0](USER_GUIDE.md#20-quick-smoke-test-recommended-after-every-refactor)).
> If `hw-smoke` is green, this full 14-phase plan is for release / refactor
> sign-off — not for routine inner-loop verification. If `hw-smoke` fails, the
> failed check ID maps directly to a specific phase below (e.g. `gateway-health`
> / `quote-probe` → Phase 2; `pico-flash-test` → Phase 4).

---

#### Table of contents

1. [Hardware inventory](#1-hardware-inventory)
2. [Software preconditions](#2-software-preconditions)
3. [Conventions](#3-conventions)
4. [Run log](#4-run-log)
5. [Regression dossier](#5-regression-dossier)
6. [Phase 0 — Dev-Host baseline (offline)](#phase-0--dev-host-baseline-offline)
7. [Phase 1 — Docker toolchains](#phase-1--docker-toolchains)
8. [Phase 2 — Gateway connectivity](#phase-2--gateway-connectivity)
9. [Phase 3 — Gateway sync](#phase-3--gateway-sync)
10. [Phase 4 — Pico flash + validate (legacy Make)](#phase-4--pico-flash--validate-legacy-make)
11. [Phase 5 — Uno flash + validate (legacy Make)](#phase-5--uno-flash--validate-legacy-make)
12. [Phase 6 — Multi-app banners (lab\_stack)](#phase-6--multi-app-banners-lab_stack)
13. [Phase 7 — I2C](#phase-7--i2c)
14. [Phase 8 — Gateway-native binary](#phase-8--gateway-native-binary)
15. [Phase 9 — SSD1306 demos (smoke)](#phase-9--ssd1306-demos-smoke)
16. [Phase 10 — Bootstrap orchestration](#phase-10--bootstrap-orchestration)
17. [Phase 11 — CLI mode (`CEDE_USE_CLI=1`)](#phase-11--cli-mode-cede_use_cli1)
18. [Phase 12 — Negative tests](#phase-12--negative-tests)
19. [Phase 13 — Scaffolding cycle (`cede new-app`)](#phase-13--scaffolding-cycle-cede-new-app)
20. [Phase 14 — Tear-down / leave system green](#phase-14--tear-down--leave-system-green)

---

#### 1. Hardware inventory

Before starting, confirm and record:

| Item              | Expected / template                                        | Yours |
| ----------------- | ---------------------------------------------------------- | ----- |
| Pi model          | Raspberry Pi 3B or newer, 64-bit Raspberry Pi OS Lite      |       |
| Pi hostname       | `cede-pi.local` (mDNS) reachable via SSH                   |       |
| Pi I2C bus        | `/dev/i2c-1` enabled (`sudo raspi-config` → I2C → enable)  |       |
| Pico (cede-rp2)   | USB CDC; `/dev/serial/by-id/usb-Raspberry_Pi_Pico_*-if00`  |       |
| Uno (cede-uno)    | USB serial; `/dev/serial/by-id/usb-Arduino_*-if00`         |       |
| Level shifter     | TXS0108E or similar bidirectional, 3.3 V ⇄ 5 V             |       |
| I2C wiring        | Pico GP0/1, Uno A4/A5, Pi SDA/SCL — see `lab/pi/docs/bus-wiring.md` |  |
| OLED 1 @ 0x3c     | optional (Phase 9)                                          |      |
| OLED 2 @ 0x3d     | optional (Phase 9)                                          |      |
| Bus speed         | `/boot/firmware/config.txt` should pin `dtparam=i2c_arm_baudrate=100000` (verify with `ssh pi@… "grep i2c_arm /boot/firmware/config.txt"`); `400000` is known-bad with typical level shifters and breaks Uno register reads (see Phase 7) |  |

The I2C address map this plan assumes:

| Address | Device                              |
| ------- | ----------------------------------- |
| 0x42    | Pico `hello_lab` / `lab_stack`      |
| 0x43    | Uno `hello_lab` / `lab_stack`       |
| 0x3c    | SSD1306 #1 (optional)               |
| 0x3d    | SSD1306 #2 (optional)               |

---

#### 2. Software preconditions

On the Dev-Host:

- Docker daemon running (`docker info` succeeds).
- [`uv`](https://docs.astral.sh/uv/) installed and on `PATH`.
- Repository cloned; `uv sync` has been run at least once.
- `ssh-agent` has a key registered that is also in `~/.ssh/authorized_keys` on
  the Pi (test with `ssh pi@cede-pi.local true`).
- `mdns` works: `getent hosts cede-pi.local` resolves.
- Repo is on a clean working tree (`git status` shows no unstaged changes that
  could shift `git rev-parse --short=12 HEAD`).
- `config/lab.yaml` exists (copy from `config/lab.example.yaml` if not).

On the Pi gateway:

- `picotool`, `avrdude`, `python3`, `i2cdetect`/`i2cget`, `rsync`,
  `pyserial` installed (Phase 2.1 verifies).
- `pi` user can flash without sudo (member of `dialout`, `plugdev`).

---

#### 3. Conventions

Set these once at the start of every validation run so every digest assertion
in this document evaluates against a deterministic value:

```bash
cd /path/to/cede
export CEDE_IMAGE_ID="$(git rev-parse --short=12 HEAD)"
echo "CEDE_IMAGE_ID=${CEDE_IMAGE_ID}"   # e.g. aec771d88ba3
```

If the Docker toolchain has previously left root-owned `build/` directories in
the source tree (a side effect of containers running as root), reclaim them
before Phase 0 to avoid `PermissionError` later:

```bash
docker run --rm -v "$PWD:/ws" -w /ws alpine sh -c \
  "chown -R $(id -u):$(id -g) lab/pico/*/build lab/uno/*/build validation-apps/*/*/build 2>/dev/null || true"
```

> **Note on `/dev/ttyACM*` ordering:** the kernel assigns `ttyACM0`, `ttyACM1`,
> etc. in the order USB devices enumerate, so a Pi reboot (or hot-plug
> sequence change) can swap the Pico and Uno paths between runs. Every flow
> in this plan resolves the device via the stable
> `/dev/serial/by-id/usb-{Raspberry_Pi_Pico,Arduino}_*-if00` symlink (see
> STEP-2.4 / STEP-2.5), so the ordering does **not** matter for correctness.
> If a step ever pins a literal `/dev/ttyACM<N>` you have found a regression —
> file it as a new B-NN entry.

**Pass criterion for the whole plan:** every step in every phase passes, OR the
operator records a documented "known-fail" with a written justification in
the Run log.

---

#### 4. Run log

Operator fills one row per session. Per-phase column accepts `PASS`, `FAIL`,
or `SKIP-<reason>`.

| Date (UTC) | Operator | Git SHA | P0 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 | P11 | P12 | P13 | P14 |
| ---------- | -------- | ------- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- |
|            |          |         |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |
|            |          |         |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |

---

#### 5. Regression dossier

Every entry below is a real bug surfaced during prior validation sessions.
Each is gated by one or more step IDs further down the document. **If you
introduce a new bug that survives this checklist, append a new B-NN row AND
the step(s) that should have caught it.**

| ID    | Bug                                                                                                       | Gated by                       |
| ----- | --------------------------------------------------------------------------------------------------------- | ------------------------------ |
| B-1   | SSH arg quoting lost across `gateway/scripts/devhost_pi_gateway.sh::_remote_repo` heredoc                  | STEP-2.1, STEP-6.1, STEP-6.2   |
| B-2   | `gateway/scripts/cede_firmware_attest.py` hardcoded `hello_lab` banner prefix                              | STEP-6.1, STEP-6.2, STEP-N-3   |
| B-3   | `src/cede/build.py` did not substitute `{sketch_dir}` / `{app_dir}` placeholders                           | STEP-11.2                      |
| B-4   | Uno sketch directory name didn't match `.ino` filename → arduino-cli rejection                            | STEP-11.2                      |
| B-5   | Root-owned `build/` dirs after Docker → CLI digest-sidecar write fails with `PermissionError`              | STEP-11.1, STEP-11.2           |
| B-6   | `SSHTransport.run_command` joined args without shell-quoting; multi-word args lost                         | STEP-11.3, STEP-11.7           |
| B-7   | `cede deploy` didn't auto-resolve `{port}` → `avrdude` got empty `-P`                                      | STEP-11.4, STEP-11.7           |
| B-8   | `cede validate` `cat`-only read couldn't wake Pico USB-CDC (no DTR toggle) → spurious timeout              | STEP-11.5, STEP-11.7           |
| B-9   | `cede flash-test` defaulted to `Path(".")` for artifact discovery → "no artifact found"                    | STEP-11.7                      |
| B-10  | Makefile `cede-flash-test-*` didn't plumb `MODE` to the CLI → silently fell back to direct mode            | STEP-11.7                      |
| B-11  | Pico/Uno firmware built without `CEDE_IMAGE_ID` shows `digest=unknown` → validate mismatch                 | STEP-N-1                       |
| B-12  | `docker-compose.yml` had `volumes: ../..:/workspace` (mounted the wrong tree)                              | STEP-1.3, STEP-1.4             |
| B-13  | SSH `bash -lc` polluted stdout with rfkill noise → serial port resolver returned `'Wi-Fi'`                 | STEP-2.4, STEP-2.5             |
| B-14  | Gateway Python (`pi_bootstrap.py`, `lab_i2c_matrix_validate.py`, etc.) used wrong `Path().parents[N]` index | STEP-7.5                      |
| B-15  | Empty `GATEWAY_REPO_ROOT=""` env (vs unset) → `cd ""` failure instead of `~/cede` fallback                 | STEP-N-4                       |
| B-16  | `container-test-baseline` invoked compose via `lab/docker/docker-compose.yml` (symlink) → `..` resolved to `lab/`, mounting the wrong tree at `/workspace` | STEP-0.4                       |
| B-17  | `cede debug` referenced non-existent dataclass attributes (`DebugConfig.serial_command`, `.gdb_command`, `SerialConfig.baud`) → both `--method serial` and `--method gdb` crashed with `AttributeError` before opening anything | STEP-0.5                       |
| B-18  | `cede new-app --target uno` scaffold wrote `entrypoint: build/<app>.hex` into `cede_app.yaml` but the actual build artifact is `build/<source-ino-stem>.ino.hex` (template `.ino` is named `app.ino`) → `cede deploy` from inside the app dir can't locate the artifact | STEP-13.2                      |
| B-19  | `cede new-app` scaffold templates emit the banner once at boot and bake `CEDE_IMAGE_ID="unknown"` (no `-DCEDE_IMAGE_ID` in `CMakeLists.txt`, no `gen_cede_image_id.sh` in build_command) → `cede validate` on fresh scaffolds reads only the loop output and fails with `no digest= found` / `digest=unknown` | STEP-13.3                      |
| B-20  | `make container-test-baseline` pytest invocation inside `orchestration-dev` lacks `PYTHONPATH=/workspace/src` and tries to collect `tests/test_ssd1306_eyes_dirty_stats.py` (PIL not in image) → collection-time `ModuleNotFoundError` | STEP-0.4                       |

---

#### Per-step template

Every step in every phase uses this layout — copy/paste the command exactly,
then grep the output for the listed tokens.

```
##### STEP-X.Y — <title>
Command:
    <exact shell command>
Expected (must appear in output, exit 0 unless noted):
    - <token #1>
    - <token #2>
Catches: B-NN | smoke
On failure, investigate: <pointer>
```

---

#### Phase 0 — Dev-Host baseline (offline)

Confirms the Python environment, configs, and JSON schemas are coherent.
No hardware required. Should take well under a minute.

##### STEP-0.1 — Python unit suite

Command:
```bash
make validate
```
Expected:
- All collected tests pass (e.g. **244 passed**, **8 deselected** for `@pytest.mark.hardware` — those run via **`make validate-target`** with **`CEDE_RUN_HARDWARE_*`** on a bench).
- Final line shows `passed` and `deselected` (or `skipped` for other markers); no `failed`.

Catches: smoke (CLI/`config.py`/`identity.py`/`transport.py` regressions).
On failure: re-run individual files with `uv run pytest tests/<file>.py -v -m "not hardware"`.

##### STEP-0.2 — Lab schema test

Command:
```bash
make test-config-local
```
Expected:
- `2 passed`.

Catches: `config/lab.schema.json` drift vs `config/lab.example.yaml`.
On failure: see `tests/test_config_schema.py`.

##### STEP-0.3 — `cede --help` smoke

Command:
```bash
uv run cede --help
```
Expected:
- Subcommands listed: `build`, `deploy`, `validate`, `flash-test`, `run`,
  `debug`, `new-app`.

Catches: pyproject `[project.scripts]` regression.

##### STEP-0.4 — Container test baseline

Command:
```bash
make container-test-baseline
```
Expected:
- Builds `pico-dev`, `arduino-dev`, `orchestration-dev` images (cached after
  first run).
- Smoke + Pico + Uno builds succeed.
- In-container pytest reports `203 passed, … skipped` (the 3 host-only
  subprocess-based tests in `test_cli_build.py::test_generate_from_git`,
  `test_firmware_digest.py::test_make_print_firmware_digest_digest_override`,
  and `test_pi_cloud_init_render.py` are skipped via the documented divergence
  and are **not** expected to pass inside `orchestration-dev`).
- **No** `file or directory not found: tests/` error (would indicate B-16).
- **No** `ModuleNotFoundError: No module named 'cede'` (would indicate the
  `PYTHONPATH=/workspace/src` plumbing regressed — B-20).
- **No** `ModuleNotFoundError: No module named 'PIL'` (would indicate
  `--ignore=tests/test_ssd1306_eyes_dirty_stats.py` was dropped from the
  invocation — B-20).

Catches: B-16, B-20.
On failure: confirm `docker compose -f docker/docker-compose.yml config | grep -A1 volumes` shows `source: <repo-root>` (not `<repo-root>/lab`).

##### STEP-0.5 — `cede debug` argv smoke

Command:
```bash
timeout 2 uv run cede debug --target pico --method serial --port /dev/null 2>&1 | head -5
uv run cede debug --target pico --method gdb --elf /dev/null 2>&1 | head -3
```
Expected (serial):
- A line `[cede debug] serial: picocom -b 115200 /dev/null` (or `minicom -b 115200 -D /dev/null` / `screen /dev/null 115200`, depending on which tool is on `PATH`).
- An exit-hint line referencing the chosen tool's quit chord.
- **No** `AttributeError: 'DebugConfig' object has no attribute 'serial_command'`.
- **No** `AttributeError: 'SerialConfig' object has no attribute 'baud'`.

Expected (gdb):
- A line `[cede debug] gdb: openocd -f interface/cmsis-dap.cfg -f target/pico.cfg -c 'gdb_port 3333' & sleep 1 && gdb-multiarch -ex 'target remote :3333' -ex 'load' '/dev/null'`.
- **No** `AttributeError: 'DebugConfig' object has no attribute 'gdb_command'`.
- (Whether `openocd`/`gdb-multiarch` are actually installed is out of scope
  here — this step gates the command-construction code path.)

Catches: B-17.

---

#### Phase 1 — Docker toolchains

Builds the Pico and Arduino toolchain images, then compiles the reference
firmware. Each `build/` directory must contain an artifact at the expected
path. Note: containers run as root and produce root-owned files — the chown
one-liner from [§3 Conventions](#3-conventions) is the cleanup.

##### STEP-1.1 — Build toolchain images

Command:
```bash
make -C lab/docker build-images
```
Expected:
- `pico-dev` and `arduino-dev` images present after.
- Verify with `docker images | grep -E 'cede/(pico|arduino)-dev'` — both
  tagged `local`.

Catches: Dockerfile drift, base image registry outage.

##### STEP-1.2 — Toolchain smoke

Command:
```bash
make -C lab/docker smoke
```
Expected:
- `arduino-cli Version: …` line present.
- `cc (Debian …` (gcc inside `orchestration-dev`) present.

Catches: B-12 (wrong workspace mount), broken toolchain image.

##### STEP-1.3 — Pico `hello_lab` build

Command:
```bash
make -C lab/docker pico-build CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- `Linking CXX executable hello_lab.elf`.
- File exists: `lab/pico/hello_lab/build/hello_lab.uf2`.

Catches: B-12 (volume mount), Pico SDK regression.
On failure: `docker compose -f docker/docker-compose.yml config | grep volumes`
should show `..:/workspace` (one parent, not two).

##### STEP-1.4 — Uno `hello_lab` build

Command:
```bash
make -C lab/docker uno-build CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- `Used platform … arduino:avr`.
- File exists: `lab/uno/hello_lab/build/hello_lab.ino.hex`.

Catches: B-12, arduino-cli core install regression.

##### STEP-1.5 — Pico `lab_stack` build

Command:
```bash
make -C lab/docker pico-build-lab-stack CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- `Linking CXX executable lab_stack.elf`.
- File exists: `lab/pico/lab_stack/build/lab_stack.uf2`.

Catches: multi-app build regression.

##### STEP-1.6 — Uno `lab_stack` build

Command:
```bash
make -C lab/docker uno-build-lab-stack CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- File exists: `lab/uno/lab_stack/build/lab_stack.ino.hex`.

Catches: multi-app Uno build regression.

##### STEP-1.7 — Gateway-native (`hello_gateway`) build

Command:
```bash
make pi-gateway-build-native-hello CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- aarch64 ELF produced under `lab/pi/hello_gateway/build/` (or the
  configured `paths.gateway_native_build`).

Catches: qemu/binfmt regression on amd64 hosts, `orchestration-dev` image rot.

---

#### Phase 2 — Gateway connectivity

Confirms the Dev-Host ↔ gateway plumbing: SSH reaches the Pi, the remote shell
does not leak login-shell noise into stdout (B-13), and arg quoting survives
the heredoc / `printf %q` boundary (B-1).

##### STEP-2.1 — Health

Command:
```bash
make pi-gateway-health
```
Expected:
- Exactly the line `health: ok (picotool, avrdude, python3 present)`.

Catches: B-1, B-15.
On failure: try `ssh pi@cede-pi.local true` (raw SSH). If that works but
`make` fails, the bug is in `gateway/scripts/devhost_pi_gateway.sh::_remote_repo`
or `cmd_health`.

##### STEP-2.2 — Subtarget enumeration

Command:
```bash
make pi-gateway-subtarget-check
```
Expected:
- `health: ok …`
- Two `lrwxrwxrwx … usb-Arduino_*` and `usb-Raspberry_Pi_Pico_*` symlink lines.

Catches: USB enumeration broken, udev rules missing.

##### STEP-2.3 — Print serial paths

Command:
```bash
make pi-gateway-print-serial
```
Expected:
- One line per `/dev/ttyACM*` device.

Catches: smoke.

##### STEP-2.4 — Resolve Pico port

Command:
```bash
make pi-gateway-resolve-port-pico
```
Expected:
- A single line printed: `/dev/serial/by-id/usb-Raspberry_Pi_Pico_*-if00`.
- **No** lines containing `rfkill`, `Wi-Fi`, or other warning text.

Catches: B-13 (login shell pollution), B-1.

##### STEP-2.5 — Resolve Uno port

Command:
```bash
make pi-gateway-resolve-port-uno
```
Expected:
- A single line: `/dev/serial/by-id/usb-Arduino_*-if00`.

Catches: B-13, B-1.

---

#### Phase 3 — Gateway sync

Pushes the gateway-side sparse tree (`gateway/scripts/`, `lab/pi/`) to
`pi@cede-pi.local:~/cede` so the legacy Make targets and CLI SSH commands
have what they need.

##### STEP-3.1 — Push sparse tree

Command:
```bash
make sync-pi-gateway-flash-deps
```
Expected:
- rsync summary `total size is ….` and `speedup is …`.
- Final line includes `gateway flash deps synced to pi@…:~/cede`.

Catches: rsync misconfiguration, network outage.

##### STEP-3.2 — Verify remote layout

Command:
```bash
ssh pi@cede-pi.local 'ls -1 ~/cede/lab/pi/scripts | head -5; echo ----; ls -1 ~/cede/gateway/scripts | head -5'
```
Expected:
- Both directory listings non-empty.
- `devhost_pi_gateway.sh`, `cede_firmware_attest.py`, `pi_validate_*` files
  visible on the gateway side.

Catches: stale `.gitignore` / `rsync --exclude` regression.

---

#### Phase 4 — Pico flash + validate (legacy Make)

End-to-end: Pi → BOOTSEL → flash → reboot → serial banner attestation.

##### STEP-4.1 — Flash Pico

Command:
```bash
make pi-gateway-flash-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- `Loading into Flash:` and `Verifying Flash:` progress bars reach 100 %.
- Final picotool line `The device was rebooted to start the application.`

Catches: picotool/Pi USB issue, BOOTSEL mount latency.

##### STEP-4.2 — Validate Pico serial banner

Command:
```bash
make pi-gateway-validate-pico FIRMWARE_DIGEST="${CEDE_IMAGE_ID}"
```
Expected:
- `expected-digest: ${CEDE_IMAGE_ID}`
- `digest-banner: CEDE hello_lab rp2 ok digest=${CEDE_IMAGE_ID} …`
- `validate: ok (cede-rp2 serial banner present)`

Catches: B-2 (banner hardcode regression), serial DTR regression.

##### STEP-4.3 — Flash-test Pico (build → flash → validate)

Command:
```bash
make pi-gateway-flash-test-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- All STEP-4.1 + STEP-4.2 tokens present.
- A `tests/results/run_<UTC>_pico_*.json` file appears.

Catches: composite target regression.

---

#### Phase 5 — Uno flash + validate (legacy Make)

##### STEP-5.1 — Flash Uno

Command:
```bash
make pi-gateway-flash-uno SKIP_SYNC=1
```
Expected:
- avrdude shows `Writing | … | 100 %` and `Reading | … | 100 %` then
  `avrdude done.`

Catches: avrdude/Pi serial regression, missing dialout group.

##### STEP-5.2 — Validate Uno serial banner

Command:
```bash
make pi-gateway-validate-uno FIRMWARE_DIGEST="${CEDE_IMAGE_ID}"
```
Expected:
- `digest-banner: CEDE hello_lab ok digest=${CEDE_IMAGE_ID} …`
- `validate: ok (serial banner present)`

Catches: B-2, Uno banner shape regression.

##### STEP-5.3 — Flash-test Uno

Command:
```bash
make pi-gateway-flash-test-uno SKIP_SYNC=1
```
Expected:
- STEP-5.1 + STEP-5.2 tokens present.
- `tests/results/run_<UTC>_uno_*.json` appears.

Catches: composite target regression.

---

#### Phase 6 — Multi-app banners (`lab_stack`)

**Critical regression gate.** These two steps simultaneously exercise multi-word
`--expect` arg propagation across SSH (B-1) and per-app banner attestation
(B-2). If B-1 or B-2 regresses, this phase fails with either
`unrecognized arguments: rp2 ok …` or `missing hello_lab serial banner` even
though the firmware is correct.

##### STEP-6.1 — Pico `lab_stack` flash-test

Command:
```bash
make pi-gateway-flash-test-pico-lab-stack SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- `digest-banner: CEDE lab_stack rp2 ok digest=${CEDE_IMAGE_ID} …`
- `validate: ok (cede-rp2 serial banner present)`
- **No** `unrecognized arguments` error.
- **No** `missing hello_lab serial banner` error.

Catches: B-1, B-2.

##### STEP-6.2 — Uno `lab_stack` flash-test

Command:
```bash
make pi-gateway-flash-test-uno-lab-stack SKIP_SYNC=1
```
Expected:
- `digest-banner: CEDE lab_stack ok digest=${CEDE_IMAGE_ID} …`
- `validate: ok (serial banner present)`

Catches: B-1, B-2.

---

#### Phase 7 — I2C

I2C wiring sanity, then the per-pair register reads driven by
`config/lab.yaml::i2c_matrix`. With `dtparam=i2c_arm_baudrate=100000` the
register reads to both Pico and Uno are clean.

> **Known hardware limitation (still applies if bus speed is bumped):** the
> Pi's I2C clock at 400 kHz is not cleanly supported by typical 3.3 V ⇄ 5 V
> level shifters (TXS0108E and similar). At 400 kHz, register reads to the
> Uno return garbage (e.g. `0xe7` instead of `0xce`) or `Error: Read failed`.
> Stay at 100 kHz unless you have a level shifter known to handle 400 kHz
> cleanly.
>
> **Pre-flight (every session):**
> ```bash
> ssh pi@cede-pi.local "grep -E '^dtparam=i2c_arm' /boot/firmware/config.txt"
> ```
> Expected: an active `dtparam=i2c_arm_baudrate=100000` line (and any
> `400000` line commented out). If absent, edit the config file, reboot the
> Pi, and re-run Phase 2 before continuing.

##### STEP-7.1 — `i2cdetect`

Command:
```bash
make pi-gateway-diagnose-i2c
```
Expected:
- `0x42` (Pico) and `0x43` (Uno) appear in the `i2cdetect` map.
- Optional: `0x3c` and/or `0x3d` for SSD1306 displays.

Catches: physical wiring fault, pull-up missing, I2C disabled.

##### STEP-7.2 — Pi → Pico register read

Command:
```bash
make pi-gateway-validate-i2c-pi-to-pico
```
Expected:
- The first line is the bare `i2cget` output — exactly `0xce`.
- Then the Pico serial banner re-validates with `digest=${CEDE_IMAGE_ID}`.
- Make exits 0.

Catches: Pico firmware I2C handler regression.

##### STEP-7.3 — Pi → Uno register read

Command:
```bash
make pi-gateway-validate-i2c-pi-to-uno
```
Expected:
- The first line is the bare `i2cget` output — exactly `0xce`.
- Then the Uno serial banner re-validates with `digest=${CEDE_IMAGE_ID}`.
- Make exits 0.

If you instead see `0xe7`, `0xff`, or `Error: Read failed`, the bus is most
likely running at 400 kHz: see the pre-flight at the top of Phase 7 and drop
to 100 kHz before retrying.

Catches: Uno I2C handler regression at 100 kHz; level-shifter / bus-speed
misconfiguration above.

##### STEP-7.4 — Pi → both (sequential)

Command:
```bash
make pi-gateway-validate-i2c-both
```
Expected:
- One line `Pico 0x42 reg0: 0xce`.
- One line `Uno 0x43 reg0: 0xce`.
- Make exits 0.

##### STEP-7.5 — Lab-matrix driven validation

Command:
```bash
make pi-gateway-validate-i2c-from-lab
```
Expected:
- One PASS line per enabled pair in `config/lab.yaml::i2c_matrix.pairs`.
- **No** `cd into empty string` error.
- **No** rfkill / Wi-Fi text on stdout.

Catches: B-13, B-14, B-15.
On failure: run `python3 lab_i2c_matrix_validate.py --help` to confirm
`--gateway-repo` default is `~/cede`, not empty string.

---

#### Phase 8 — Gateway-native binary

Validates the aarch64 `hello_gateway` flow: build on the Dev-Host (via
qemu/binfmt), scp to the Pi, execute, attest stdout banner + digest.

##### STEP-8.1 — Build native gateway hello

Command:
```bash
make pi-gateway-build-native-hello CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- ELF produced (path in `paths.gateway_native_build` of `config/lab.yaml`).

Catches: qemu/binfmt regression, missing aarch64 toolchain in
`orchestration-dev` image.

##### STEP-8.2 — Validate gateway-native banner

Command:
```bash
make pi-gateway-validate-gateway-native FIRMWARE_DIGEST="${CEDE_IMAGE_ID}"
```
Expected:
- Binary runs on Pi.
- `CEDE hello_gateway ok` line on stdout with `digest=${CEDE_IMAGE_ID}`.
- `validate: ok …`

Catches: B-2 (gateway attestation path), aarch64 ELF execution regression.

---

#### Phase 9 — SSD1306 demos (smoke)

These are long-running interactive demos. They are useful as a smoke test of
the gateway's Python+I2C+SSD1306 stack but should **not** run to completion.
Start, observe one frame or banner line, kill with Ctrl-C.

Skip this phase if you have no SSD1306 displays attached; mark `SKIP-no-oled`.

##### STEP-9.1 — `ssd1306_eyes`

Command:
```bash
make pi-gateway-ssd1306-eyes
```
Expected (within ~5 s):
- `frame=` or equivalent progress line on stderr.
- Visible animation on the OLED.

Then: Ctrl-C. Step passes if the demo started cleanly.

##### STEP-9.2 — `ssd1306_dual`

Command:
```bash
make pi-gateway-ssd1306-dual
```
Expected (within ~5 s):
- Both OLEDs show distinct content.

Then: Ctrl-C. Step passes if the demo started cleanly.

---

#### Phase 10 — Bootstrap orchestration

The composite "from zero to a green lab" pipeline. If Phases 1, 4, 5 pass,
these should pass trivially — they exist to confirm the wrapper targets keep
their declared sequencing.

##### STEP-10.1 — Dev-Host baseline (composite)

Command:
```bash
make bootstrap-stage-dev-host
```
Expected:
- `test-config-local` passes.
- Pico + Uno + gateway-native builds complete.

##### STEP-10.2 — Gateway stage

Command:
```bash
make bootstrap-stage-gateway
```
Expected:
- `health: ok` + subtarget enumeration succeed.

##### STEP-10.3 — Combined dev preflight

Command:
```bash
make cede-dev-preflight
```
Expected:
- Outputs of 10.1 and 10.2 combined; final exit 0.

##### STEP-10.4 — Stage-zero (Pico)

Command:
```bash
make bootstrap-stage-zero ZERO_TARGET=pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- Pico flashed, banner with `digest=${CEDE_IMAGE_ID}` present.

##### STEP-10.5 — Stage-zero (Uno)

Command:
```bash
make bootstrap-stage-zero ZERO_TARGET=uno SKIP_SYNC=1
```
Expected:
- Uno flashed, banner with `digest=${CEDE_IMAGE_ID}` present.

##### STEP-10.6 — Full bootstrap pipeline

Command:
```bash
make bootstrap-pipeline ZERO_TARGET=pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- All of dev-host → gateway → stage-zero (pico) → stage-uno succeed in order.
- Final exit 0.

Catches: target dependency rot in `Makefile`.

---

#### Phase 11 — CLI mode (`CEDE_USE_CLI=1`)

**Densest regression gate of the entire plan.** This phase alone exercises
the bulk of the `cede` CLI surface and catches B-3 through B-10. Run with
`MODE=gateway` because the lab is gateway-attached; the negative N-5 covers
the no-MODE direct fallback.

##### STEP-11.1 — CLI build Pico

Command:
```bash
CEDE_USE_CLI=1 make cede-build-pico
```
Expected:
- `[cede build] target=pico digest=…`
- `[cede build] artifact: …/validation-apps/hello_lab/pico/build/hello_lab.uf2`
- `[cede build] sidecar:  …/hello_lab.uf2.digest`
- **No** `PermissionError`.

Catches: B-5.

##### STEP-11.2 — CLI build Uno

Command:
```bash
CEDE_USE_CLI=1 make cede-build-uno
```
Expected:
- `[cede build] target=uno digest=…`
- `[cede build] artifact: …/validation-apps/hello_lab/uno/build/hello_lab.ino.hex`
- **No** `Can't open sketch: main file missing` error.
- **No** `Can't open sketch: no such file or directory: …/{sketch_dir}` error.

Catches: B-3, B-4, B-5.

##### STEP-11.3 — CLI deploy Pico (gateway mode)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-deploy-pico
```
Expected:
- `[cede deploy] pre-flash: picotool reboot -uf`
- `The device was asked to reboot into BOOTSEL mode.`
- `Loading into Flash:` progress to 100 %.
- `[cede deploy] OK`
- **No** `picotool help` output (would signal B-6).

Catches: B-6.

##### STEP-11.4 — CLI deploy Uno (gateway mode)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-deploy-uno
```
Expected:
- `[cede deploy] flash: avrdude -p atmega328p -c arduino -P /dev/serial/by-id/usb-Arduino_*-if00 -b 115200 -D -U flash:w:/tmp/hello_lab.ino.hex:i`
  (port substituted, **not** empty).
- avrdude `Writing | … | 100 %` and `Reading | … | 100 %` lines.
- **No** `cannot open port -b` error.

Catches: B-6, B-7.

##### STEP-11.5 — CLI validate Pico (gateway mode)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-validate-pico DIGEST="${CEDE_IMAGE_ID}"
```
Expected:
- `[cede validate] target=pico expected_digest=${CEDE_IMAGE_ID}`
- `[cede validate] PASSED: digest=${CEDE_IMAGE_ID}`
- **No** `FAILED: no serial output (timeout)`.

Catches: B-8.

##### STEP-11.6 — CLI validate Uno (gateway mode)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-validate-uno DIGEST="${CEDE_IMAGE_ID}"
```
Expected:
- `[cede validate] PASSED: digest=${CEDE_IMAGE_ID}`

Catches: regression in port-resolution / DTR handling for Uno.

##### STEP-11.7 — CLI flash-test Pico (composite)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-flash-test-pico
```
Expected:
- All of STEP-11.3 + STEP-11.5 tokens present.
- **No** `[cede flash-test] ERROR: no artifact found`.

Catches: B-6, B-8, B-9, B-10.

##### STEP-11.8 — CLI flash-test Uno (composite)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-flash-test-uno
```
Expected:
- All of STEP-11.4 + STEP-11.6 tokens present.

Catches: B-6, B-7, B-9, B-10.

##### STEP-11.9 — CLI run Pico (build + deploy + validate)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-run-pico
```
Expected:
- `[cede run] build + deploy + validate target=pico`
- `[cede build] artifact: …`
- `[cede deploy] OK`
- `[cede validate] PASSED: digest=…`

Catches: composite `run_full` regression.

##### STEP-11.10 — CLI run Uno (build + deploy + validate)

Command:
```bash
CEDE_USE_CLI=1 MODE=gateway make cede-run-uno
```
Expected:
- Same shape as 11.9 with `target=uno`.

Catches: composite `run_full` regression for Uno.

---

#### Phase 12 — Negative tests

Five named negative tests, each a single command and an exact expected error
string. These are the inversions of bugs we fixed; they keep the fixes honest.

##### STEP-N-1 — Stale digest (`digest=unknown`)

Setup:
```bash
unset CEDE_IMAGE_ID
make -C lab/docker pico-build
```
Then flash and validate against the canonical digest:
```bash
export CEDE_IMAGE_ID="$(git rev-parse --short=12 HEAD)"
make pi-gateway-flash-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
make pi-gateway-validate-pico FIRMWARE_DIGEST="${CEDE_IMAGE_ID}" || echo "EXPECTED FAIL"
```
Expected:
- `validate: fail (digest mismatch: device has digest='unknown', expected digest='${CEDE_IMAGE_ID}')`
- Non-zero exit.
- Then rebuild + re-flash with `CEDE_IMAGE_ID` set to leave system green
  (Phase 13 also does this).

Catches: B-11 — confirms the attestation chain rejects un-stamped firmware.

##### STEP-N-2 — Wrong digest (mismatch error format)

Setup:
```bash
make -C lab/docker pico-build CEDE_IMAGE_ID=deadbeefdead
make pi-gateway-flash-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
make pi-gateway-validate-pico FIRMWARE_DIGEST="${CEDE_IMAGE_ID}" || echo "EXPECTED FAIL"
```
Expected:
- `validate: fail (digest mismatch: device has digest='deadbeefdead', expected digest='${CEDE_IMAGE_ID}')`

Catches: regression in `digest_mismatch_message` formatting.

##### STEP-N-3 — Wrong banner expectation

Setup: flash `hello_lab` Pico with the canonical digest, then validate with
a deliberately-wrong banner string:
```bash
make pi-gateway-flash-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
PICO_SERIAL_EXPECT="totally bogus banner" \
  make pi-gateway-validate-pico FIRMWARE_DIGEST="${CEDE_IMAGE_ID}" || echo "EXPECTED FAIL"
```
Expected:
- `validate: fail (missing serial banner (expected prefix: 'totally bogus banner'))`

Catches: B-2 — confirms `attestation_failure_reason` honors `expected_prefix`
and the per-app banner injection is wired end-to-end.

##### STEP-N-4 — Empty `GATEWAY_REPO_ROOT`

Command:
```bash
GATEWAY_REPO_ROOT="" make pi-gateway-health
```
Expected:
- Same successful output as STEP-2.1 (`health: ok …`).
- The empty string must fall back to `~/cede`, **not** trigger
  `cd: : No such file or directory`.

Catches: B-15.

##### STEP-N-5 — CLI direct-mode without explicit `MODE`

Command:
```bash
CEDE_USE_CLI=1 make cede-flash-test-pico
```
Expected (one of):
- Succeeds via Direct-Attach (if a Pico is plugged into the Dev-Host's USB).
- Fails with a clear message — e.g. `[cede deploy] FAILED` or
  `Loading into Flash` never starts — but **must not** silently emit
  `picotool help` text as if `picotool` was invoked with no args (that
  signature is the B-6 SSH-quoting regression). The Uno deploy in this
  config should similarly fail visibly, not silently.

Catches: B-6, B-10 (the absence of `MODE=gateway` previously masked these
because of how the Makefile composes flags).

---

#### Phase 13 — Scaffolding cycle (`cede new-app`)

Exercises the scaffold-→-build-→-deploy-→-validate path end-to-end with a
fresh app name, so the templates and the `cede_app.yaml` they generate are
verified to be consistent with what the build and validation pipelines
actually do. **Important:** this phase mutates the working tree under
`demo-apps/`; Phase 14 (Tear-down) reclaims the directories.

The known-bad behaviours documented in B-18 and B-19 mean a naïve "scaffold
and run" will fail today. The steps below capture the *current* expectation
so the plan still gates regressions even before the templates are fixed —
when the templates are updated to (a) emit a repeating banner and (b) inject
`CEDE_IMAGE_ID`, the expectations marked `EXPECTED FAIL (B-19)` flip to
`EXPECTED PASS` without changing the rest of the phase.

##### STEP-13.1 — Scaffold a Pico app

Command:
```bash
rm -rf demo-apps/hv_scaffold && \
uv run cede new-app hv_scaffold --target pico
```
Expected:
- `[cede new-app] Created …/demo-apps/hv_scaffold/pico`.
- Files listed: `CMakeLists.txt`, `cede_app.yaml`, `src/main.c`.
- `cede_app.yaml` declares `application_id: "hv_scaffold"`, `target: pico`,
  `category: user`, `entrypoint: "build/hv_scaffold.uf2"`, and
  `resources.usb_serial.banner_prefix: "CEDE hv_scaffold rp2 ok"`.

Catches: scaffolder template drift, missing `--category` propagation
(historical: previously hardcoded `category: user`).

##### STEP-13.2 — Scaffold an Uno app and inspect entrypoint

Command:
```bash
rm -rf demo-apps/hv_scaffold/uno && \
uv run cede new-app hv_scaffold --target uno
```
Expected:
- `[cede new-app] Created …/demo-apps/hv_scaffold/uno`.
- Files listed: `app.ino`, `cede_app.yaml`, `cede_build_id.h`.
- `cede_app.yaml` declares `entrypoint: "build/hv_scaffold.hex"`.
- **Known mismatch (B-18):** the actual artifact produced by STEP-13.4 will
  be `build/app.ino.hex`, not `build/hv_scaffold.hex`. Until the scaffolder
  is updated to rename `app.ino` → `<application_id>.ino` (or to rewrite the
  `entrypoint` to match the source filename), record `KNOWN-FAIL-B-18` in the
  Run log if any subsequent step in this phase needs `--artifact` and you
  used the yaml entrypoint instead of the real path.

Catches: B-18.

##### STEP-13.3 — Scaffold with `--output-dir` and `--category`

Command:
```bash
rm -rf validation-apps/hv_scaffold_v && \
uv run cede new-app hv_scaffold_v -t pico --output-dir validation-apps --category validation
```
Expected:
- `[cede new-app] Created validation-apps/hv_scaffold_v/pico`.
- `cede_app.yaml` declares `category: validation` (NOT `user`).

Then clean up:
```bash
rm -rf validation-apps/hv_scaffold_v
```

Catches: scaffold-template regression around `--output-dir` resolution and
`{{category}}` template substitution.

##### STEP-13.4 — Build scaffolded Pico app

Command:
```bash
uv run cede build --target pico --app-dir demo-apps/hv_scaffold/pico
```
Expected:
- `Linking CXX executable hv_scaffold.elf`.
- `[cede build] artifact: …/demo-apps/hv_scaffold/pico/build/hv_scaffold.uf2`.
- `[cede build] sidecar:  …/hv_scaffold.uf2.digest`.
- **No** `PermissionError` (would re-indicate B-5).

Catches: scaffolded `CMakeLists.txt` quality (must compile against the Pico
SDK image without manual edits).

##### STEP-13.5 — Build scaffolded Uno app

Command:
```bash
uv run cede build --target uno --app-dir demo-apps/hv_scaffold/uno
```
Expected:
- `[cede build] artifact: …/demo-apps/hv_scaffold/uno/build/app.ino.hex`.
- **Note:** filename is `app.ino.hex` — see B-18 above. When the scaffolder
  is fixed, this expectation should switch to `hv_scaffold.ino.hex`.

Catches: B-3, B-4 in the scaffolded-template flow.

##### STEP-13.6 — Deploy + validate scaffolded Pico app

Command:
```bash
uv run cede deploy --target pico --mode gateway \
  --artifact demo-apps/hv_scaffold/pico/build/hv_scaffold.uf2

### Then validate — see B-19 caveat.
uv run cede validate --target pico --digest "${CEDE_IMAGE_ID}" \
  || echo "EXPECTED FAIL (B-19): scaffold templates emit banner once + bake digest='unknown'"
```
Expected (until B-19 is fixed):
- `cede deploy` succeeds (`[cede deploy] OK`).
- `cede validate` reads `hv_scaffold running` and reports either
  `no digest= found in serial output` or
  `digest mismatch (device='unknown', expected='${CEDE_IMAGE_ID}')`.
- Record `KNOWN-FAIL-B-19` in the Run log.

Expected (after B-19 is fixed — templates loop the banner and CMake injects
`CEDE_IMAGE_ID`):
- `[cede validate] PASSED: digest=${CEDE_IMAGE_ID}`.

Catches: B-19.

##### STEP-13.7 — Restore reference firmware on the Pico

Because STEP-13.6 leaves `hv_scaffold` (not `hello_lab`) on the Pico,
re-flash the validation firmware before Phase 14:
```bash
make pi-gateway-flash-test-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- `validate: ok …` with `digest=${CEDE_IMAGE_ID}` and banner prefix
  `CEDE hello_lab rp2 ok`.

Catches: ensures the post-phase state is the same as pre-phase. Without this,
Phase 14's STEP-14.2 would still see `hv_scaffold` on the device.

---

#### Phase 14 — Tear-down / leave system green

Every validation session ends here so the next operator opens to a clean,
known-good lab.

##### STEP-14.1 — Rebuild reference firmware

Command:
```bash
make -C lab/docker pico-build CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
make -C lab/docker uno-build  CEDE_IMAGE_ID="${CEDE_IMAGE_ID}"
```
Expected:
- Both `build/hello_lab.uf2` and `build/hello_lab.ino.hex` present, fresh
  timestamps.

##### STEP-14.2 — Re-flash + verify Pico

Command:
```bash
make pi-gateway-flash-test-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
```
Expected:
- `validate: ok …` with `digest=${CEDE_IMAGE_ID}`.

##### STEP-14.3 — Re-flash + verify Uno

Command:
```bash
make pi-gateway-flash-test-uno SKIP_SYNC=1
```
Expected:
- `validate: ok …` with `digest=${CEDE_IMAGE_ID}`.

##### STEP-14.4 — Remove scaffold artifacts

Phase 13 leaves `demo-apps/hv_scaffold/` and may have left
`validation-apps/hv_scaffold_v/` in place. Clean both:
```bash
rm -rf demo-apps/hv_scaffold validation-apps/hv_scaffold_v
git status -- demo-apps validation-apps
```
Expected:
- No `hv_scaffold*` entries appear in `git status` output (working tree clean
  with respect to scaffold residue).

##### STEP-14.5 — Reclaim build directories

Command:
```bash
docker run --rm -v "$PWD:/ws" -w /ws alpine sh -c \
  "chown -R $(id -u):$(id -g) lab/pico/*/build lab/uno/*/build validation-apps/*/*/build demo-apps/*/*/build 2>/dev/null || true"
```
Expected:
- No errors.
- `find lab validation-apps demo-apps -path '*/build/*' -uid 0 2>/dev/null` returns empty.

##### STEP-14.6 — Record results

- Fill the Run log row at [§4](#4-run-log) with `PASS` / `FAIL` / `SKIP-<reason>`
  per phase (now including P14).
- File a GitHub issue (or equivalent) for every `FAIL`, citing the STEP-ID
  and the regression dossier row(s) it hit.
- If a new bug surfaced that no STEP-ID gates, append a `B-NN` row to
  [§5](#5-regression-dossier) and the matching STEP-ID(s) to this document.

---

#### Appendix — Command index

For quick reference, every command this plan runs, in order:

```text
PHASE 0  make validate                                    # pytest -m "not hardware"
         # make validate-target                           # optional bench: pytest -m hardware + CEDE_RUN_HARDWARE_*
         make test-config-local
         uv run cede --help
         make container-test-baseline                          # B-16, B-20
         timeout 2 uv run cede debug -t pico --method serial --port /dev/null   # B-17
         uv run cede debug -t pico --method gdb --elf /dev/null                  # B-17
PHASE 1  make -C lab/docker build-images
         make -C lab/docker smoke
         make -C lab/docker pico-build         CEDE_IMAGE_ID=...
         make -C lab/docker uno-build          CEDE_IMAGE_ID=...
         make -C lab/docker pico-build-lab-stack CEDE_IMAGE_ID=...
         make -C lab/docker uno-build-lab-stack  CEDE_IMAGE_ID=...
         make pi-gateway-build-native-hello    CEDE_IMAGE_ID=...
PHASE 2  make pi-gateway-health
         make pi-gateway-subtarget-check
         make pi-gateway-print-serial
         make pi-gateway-resolve-port-pico
         make pi-gateway-resolve-port-uno
PHASE 3  make sync-pi-gateway-flash-deps
         ssh pi@cede-pi.local 'ls ~/cede/lab/pi/scripts; ls ~/cede/gateway/scripts'
PHASE 4  make pi-gateway-flash-pico             SKIP_SYNC=1 PICO_WAIT_MOUNT=10
         make pi-gateway-validate-pico          FIRMWARE_DIGEST=...
         make pi-gateway-flash-test-pico        SKIP_SYNC=1 PICO_WAIT_MOUNT=10
PHASE 5  make pi-gateway-flash-uno              SKIP_SYNC=1
         make pi-gateway-validate-uno           FIRMWARE_DIGEST=...
         make pi-gateway-flash-test-uno         SKIP_SYNC=1
PHASE 6  make pi-gateway-flash-test-pico-lab-stack SKIP_SYNC=1 PICO_WAIT_MOUNT=10
         make pi-gateway-flash-test-uno-lab-stack  SKIP_SYNC=1
PHASE 7  make pi-gateway-diagnose-i2c
         make pi-gateway-validate-i2c-pi-to-pico
         make pi-gateway-validate-i2c-pi-to-uno    # known-fail @ 400 kHz
         make pi-gateway-validate-i2c-both
         make pi-gateway-validate-i2c-from-lab
PHASE 8  make pi-gateway-build-native-hello     CEDE_IMAGE_ID=...
         make pi-gateway-validate-gateway-native FIRMWARE_DIGEST=...
PHASE 9  make pi-gateway-ssd1306-eyes           # Ctrl-C after first frame
         make pi-gateway-ssd1306-dual           # Ctrl-C after first frame
PHASE 10 make bootstrap-stage-dev-host
         make bootstrap-stage-gateway
         make cede-dev-preflight
         make bootstrap-stage-zero  ZERO_TARGET=pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
         make bootstrap-stage-zero  ZERO_TARGET=uno  SKIP_SYNC=1
         make bootstrap-pipeline    ZERO_TARGET=pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
PHASE 11 CEDE_USE_CLI=1               make cede-build-pico
         CEDE_USE_CLI=1               make cede-build-uno
         CEDE_USE_CLI=1 MODE=gateway  make cede-deploy-pico
         CEDE_USE_CLI=1 MODE=gateway  make cede-deploy-uno
         CEDE_USE_CLI=1 MODE=gateway  make cede-validate-pico  DIGEST=...
         CEDE_USE_CLI=1 MODE=gateway  make cede-validate-uno   DIGEST=...
         CEDE_USE_CLI=1 MODE=gateway  make cede-flash-test-pico
         CEDE_USE_CLI=1 MODE=gateway  make cede-flash-test-uno
         CEDE_USE_CLI=1 MODE=gateway  make cede-run-pico
         CEDE_USE_CLI=1 MODE=gateway  make cede-run-uno
PHASE 12 # N-1 stale digest
         unset CEDE_IMAGE_ID; make -C lab/docker pico-build
         export CEDE_IMAGE_ID=...; make pi-gateway-flash-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
         make pi-gateway-validate-pico FIRMWARE_DIGEST=...   # EXPECT FAIL
         # N-2 wrong digest
         make -C lab/docker pico-build CEDE_IMAGE_ID=deadbeefdead
         make pi-gateway-flash-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
         make pi-gateway-validate-pico FIRMWARE_DIGEST=...   # EXPECT FAIL
         # N-3 wrong banner expectation
         PICO_SERIAL_EXPECT="totally bogus banner" \
           make pi-gateway-validate-pico FIRMWARE_DIGEST=... # EXPECT FAIL
         # N-4 empty GATEWAY_REPO_ROOT
         GATEWAY_REPO_ROOT="" make pi-gateway-health         # EXPECT PASS
         # N-5 CLI no MODE
         CEDE_USE_CLI=1 make cede-flash-test-pico            # EXPECT visible result
PHASE 13 rm -rf demo-apps/hv_scaffold
         uv run cede new-app hv_scaffold --target pico
         uv run cede new-app hv_scaffold --target uno                            # B-18
         uv run cede new-app hv_scaffold_v -t pico --output-dir validation-apps --category validation
         rm -rf validation-apps/hv_scaffold_v
         uv run cede build --target pico --app-dir demo-apps/hv_scaffold/pico
         uv run cede build --target uno  --app-dir demo-apps/hv_scaffold/uno
         uv run cede deploy   -t pico --mode gateway --artifact demo-apps/hv_scaffold/pico/build/hv_scaffold.uf2
         uv run cede validate -t pico --digest "$CEDE_IMAGE_ID"                  # B-19 KNOWN-FAIL until templates loop banner + inject digest
         make pi-gateway-flash-test-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10          # restore reference firmware
PHASE 14 make -C lab/docker pico-build CEDE_IMAGE_ID=...
         make -C lab/docker uno-build  CEDE_IMAGE_ID=...
         make pi-gateway-flash-test-pico SKIP_SYNC=1 PICO_WAIT_MOUNT=10
         make pi-gateway-flash-test-uno  SKIP_SYNC=1
         rm -rf demo-apps/hv_scaffold validation-apps/hv_scaffold_v
         docker run --rm -v $PWD:/ws -w /ws alpine sh -c 'chown -R ... demo-apps/*/*/build ...'
```
