# lab_stack — Pico + Uno demo

Multi-target application: **Pico** and **Uno** each run `lab_stack` firmware with matching `application_id`, USB serial banners, and I2C responder bytes (`0x42` on Pico, `0x43` on Uno).

## Source layout

Canonical **build directories** used by `make -C lab/docker …` and `pi-gateway-*` are:

- `lab/pico/lab_stack/`
- `lab/uno/lab_stack/`

Keep them aligned with this `demo-apps/lab_stack/` tree (same `cede_app.yaml` semantics: Pico uses the schema-style `i2c` block; extended `requires` / `i2c_slave` may appear only under `lab/` for lab-path resolution).

## Build

```bash
export DIG=$(git rev-parse --short=12 HEAD)
make -C lab/docker pico-build-lab-stack uno-build-lab-stack CEDE_IMAGE_ID="$DIG"
# or
make -C lab/docker pico-build PICO_APP=lab_stack uno-build UNO_APP=lab_stack CEDE_IMAGE_ID="$DIG"
```

## Flash, validate, I2C matrix

Follow **[lab/docs/deploy-lab-stack-app.md](../../lab/docs/deploy-lab-stack-app.md)** and **[lab/docs/staged-bootstrap.md](../../lab/docs/staged-bootstrap.md)** (copy-paste bench section). Shortcuts:

```bash
make pi-gateway-flash-test-pico-lab-stack GATEWAY=pi@cede-pi.local
make pi-gateway-flash-test-uno-lab-stack GATEWAY=pi@cede-pi.local
make pi-gateway-validate-i2c-from-lab GATEWAY=pi@cede-pi.local GATEWAY_REPO_ROOT='~/cede' \
  CEDE_LAB_CONFIG="$(pwd)/lab/config/lab.example.yaml"
```
