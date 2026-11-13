# Direct-Attach Mode (DS-12.1)

When a target MCU is plugged directly into the Dev-Host (no gateway), the `cede`
CLI operates in Direct-Attach mode. This document captures the practical
requirements discovered during the Phase 6.5 spike.

## Pico (RP2040/RP2350)

### Flash via picotool

- **Tool**: `picotool` (installed via system package or built from source)
- **Pre-flash**: `picotool reboot -f -u` puts the device into BOOTSEL mode
- **Flash**: `picotool load <artifact.uf2> -f -x` loads and executes
- **USB permissions**: The Pico in BOOTSEL mode appears as a USB mass-storage
  device. On most Linux distros, this requires no special udev rules.
- **Post-BOOTSEL serial**: After flashing, the Pico re-enumerates as a USB CDC
  serial device (`/dev/ttyACM*`). This may take 1-3 seconds.

### udev rules (recommended)

```
# /etc/udev/rules.d/99-pico.rules
# RP2040 in BOOTSEL mode
SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="0003", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="000a", MODE="0666"
# RP2040 serial (CDC)
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", MODE="0666"
```

### Docker --device passthrough

When building inside Docker, `picotool` needs USB access:

```bash
docker run --rm --device /dev/bus/usb -v $(pwd):/workspace pico-dev:local ...
```

This is **only** needed for direct-attach flash-from-container scenarios. Normal
builds do not require device access.

## Uno (ATmega328P)

### Flash via avrdude

- **Tool**: `avrdude` (installed via system package)
- **Pre-flash**: None needed (Arduino bootloader listens on serial after reset)
- **Flash**: `avrdude -p atmega328p -c arduino -P <port> -b 115200 -U flash:w:<artifact.hex>:i`
- **USB permissions**: The Uno appears as a USB serial device (`/dev/ttyUSB*` or
  `/dev/ttyACM*`). Requires the user to be in the `dialout` group.

### udev rules (recommended)

```
# /etc/udev/rules.d/99-arduino.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666"
```

### User group

```bash
sudo usermod -aG dialout $USER
# Log out and back in for group to take effect
```

## Port Resolution in Direct Mode

The `cede` CLI resolves the serial port in this order:
1. Explicit `--port /dev/ttyACM0` flag
2. `serial.device_match.by_id_glob` from target-type.yaml (stable `/dev/serial/by-id/` path)
3. `serial.device_match.fallback_globs` from target-type.yaml (matches first available)

## Validation

Direct-Attach mode has been validated to work identically to Gateway mode for
the flash and validate steps. The only difference is that commands execute
locally via `DirectTransport` instead of over SSH via `SSHTransport`.
