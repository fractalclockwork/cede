# Demo applications (`demo-apps/`)

These projects are **not** part of the core CEDE product (see DS-18); they show multi-target and gateway patterns. Each folder has a `cede_app.yaml` validated by `tests/test_app_manifest.py`.

## Index

| Demo | Targets | Role |
|------|---------|------|
| [gv2](gv2/pico/) | Pico | Minimal USB-serial banner loop (`CEDE gv2 rp2 ok digest=…`). |
| [lab_stack](lab_stack/) | Pico + Uno | Multi-target firmware + I2C responders (`0x42` / `0x43`). **Build tree:** `lab/pico/lab_stack`, `lab/uno/lab_stack` (keep in sync with this tree). |
| [ssd1306_dual](ssd1306_dual/pi/) | Pi (gateway) | Python + two SSD1306 OLEDs on Linux I2C. **Runs from:** `lab/pi/ssd1306_dual` (same files as here). |
| [ssd1306_eyes](ssd1306_eyes/pi/) | Pi (gateway) | Python cartoon eyes on dual OLEDs. **Runs from:** `lab/pi/ssd1306_eyes`. |

## Build and flash (MCU demos)

From the **repository root** on the Dev-Host, with Docker:

```bash
export DIG=$(git rev-parse --short=12 HEAD)

# gv2 (Pico) — sources under demo-apps; build via symlink lab/pico/gv2
make -C lab/docker pico-build PICO_APP=gv2 CEDE_IMAGE_ID="$DIG"
make pi-gateway-flash-pico UF2=lab/pico/gv2/build/gv2.uf2 GATEWAY=pi@cede-pi.local
make pi-gateway-validate-pico GATEWAY=pi@cede-pi.local CEDE_APPLICATION_ID=gv2 \
  PICO_SERIAL_EXPECT="CEDE gv2 rp2 ok" DIGEST="$DIG"
```

**lab_stack** (Pico + Uno): see [lab/docs/deploy-lab-stack-app.md](../lab/docs/deploy-lab-stack-app.md) and `make pi-gateway-flash-test-pico-lab-stack` / `make pi-gateway-flash-test-uno-lab-stack`.

## Run (Pi gateway demos)

Requires OLED wiring per each README and a venv on the Pi (or use Dev-Host Make wrappers that sync + SSH):

```bash
make pi-gateway-ssd1306-dual      # dual panels — Ctrl+C stops
make pi-gateway-ssd1306-eyes     # cartoon eyes
```

## See also

- [lab/docs/applications.md](../lab/docs/applications.md) — how `lab.yaml` references applications.
- [docs/USER_GUIDE.md](../docs/USER_GUIDE.md) — general `cede` / `make pi-gateway-*` workflow.
