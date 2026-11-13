# gv2 — Pico demo (minimal serial banner)

Firmware prints `CEDE gv2 rp2 ok digest=<id>` on USB CDC every few seconds. `digest` is embedded at **Docker build** time from `CEDE_IMAGE_ID` (or git short on the Dev-Host).

## Build (Docker)

From repo root:

```bash
export DIG=$(git rev-parse --short=12 HEAD)
make -C lab/docker pico-build PICO_APP=gv2 CEDE_IMAGE_ID="$DIG"
```

Artifact: `lab/pico/gv2/build/gv2.uf2` (via symlink `lab/pico/gv2` → `demo-apps/gv2/pico`).

Or build with the **CEDE CLI** (no `PICO_APP` symlink required):

```bash
uv run cede build -t pico --app-dir demo-apps/gv2/pico --digest "$(git rev-parse --short=12 HEAD)"
```

## Flash and validate (via Raspberry Pi gateway)

```bash
make pi-gateway-flash-pico \
  UF2=lab/pico/gv2/build/gv2.uf2 \
  GATEWAY=pi@cede-pi.local

make pi-gateway-validate-pico \
  GATEWAY=pi@cede-pi.local \
  CEDE_APPLICATION_ID=gv2 \
  PICO_SERIAL_EXPECT="CEDE gv2 rp2 ok" \
  DIGEST="$(git rev-parse --short=12 HEAD)"
```

Adjust `DIGEST` if you passed a different `CEDE_IMAGE_ID` into the Docker build.

## Manifest

See [cede_app.yaml](cede_app.yaml) (`category: user`, `banner_prefix` matches the printed line prefix before `digest=`).
