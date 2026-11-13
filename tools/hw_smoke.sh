#!/usr/bin/env bash
# tools/hw_smoke.sh — live-hardware smoke: fresh Docker builds, then gateway + flash + attestation.
#
# Runs a bounded sequence against the live lab (Pi gateway + Pico + Uno + I2C):
#   1. docker-version   — `docker version` (tooling present)
#   2. preflight        — `uv run cede --help`
#   3. docker-hello-lab-build — `make -C lab/docker pico-build uno-build` with $CEDE_IMAGE_ID embedded
#   4. gateway-health   — `make pi-gateway-health` reports `health: ok …`
#   5. port-pico        — Pico resolves to /dev/serial/by-id/usb-Raspberry_Pi_*
#   6. port-uno         — Uno  resolves to /dev/serial/by-id/usb-Arduino_*
#   7. i2c-0x42-pico    — `i2cget -y 1 0x42 0 b` returns 0xce
#   8. i2c-0x43-uno     — `i2cget -y 1 0x43 0 b` returns 0xce
#   9. pico-flash-test  — flash + validate Pico, banner digest = $CEDE_IMAGE_ID
#  10. quote-probe      — after Pico flash: multi-word args + digest on live serial
#  11. uno-flash-test  — flash + validate Uno, banner digest = $CEDE_IMAGE_ID
#
# Pass criterion: `check` / `check_with_retry` require a regex match in the log;
# `check_rc` requires exit status 0. Failures are counted (NOT aborted on first)
# so the operator sees the whole picture; per-step logs are kept in a tempdir until the script exits.
#
# pico-flash-test runs with bounded retry-with-backoff because the Pico flash
# path (BOOTSEL → mass-storage mount → UF2 write → CDC re-enumerate) is a USB
# state machine that occasionally drops a step on Pi hubs. All other steps are
# single-shot.
#
# Companion to docs/DEV_OP.md Part 3 (the deep release-grade plan); this
# script is intended for the inner loop after every refactor. Expect several
# minutes on a cold cache while Docker rebuilds hello_lab (override
# CEDE_HW_SMOKE_BUILD_TIMEOUT).

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

: "${CEDE_IMAGE_ID:=$(git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"
export CEDE_IMAGE_ID

: "${GATEWAY:=pi@cede-pi.local}"
export GATEWAY

# Timeouts: all ssh invocations get a short ConnectTimeout + ServerAlive probe so
# a wedged Pi fails fast (was hanging up to the kernel TCP timeout, ~2 min).
# Each `check` is wrapped in `timeout` to bound the worst case.
SSH_TIMEOUT_OPTS=(-o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 -o BatchMode=yes)
STEP_TIMEOUT="${CEDE_HW_SMOKE_STEP_TIMEOUT:-15}"       # short steps (health, ports, i2c)
FLASH_TIMEOUT="${CEDE_HW_SMOKE_FLASH_TIMEOUT:-70}"     # flash + attest steps
BUILD_TIMEOUT="${CEDE_HW_SMOKE_BUILD_TIMEOUT:-900}"    # Docker pico-build + uno-build (cold cache)
PICO_WAIT_MOUNT="${CEDE_HW_SMOKE_PICO_WAIT_MOUNT:-30}" # Pi USB mass-storage enumeration can be slow

# Retry policy for Pico flash. The Pico flash path is a USB state machine
# (BOOTSEL → mass-storage mount → UF2 write → re-enumerate as CDC-ACM), and
# transient losses on Pi USB hubs are common. A small bounded retry-with-backoff
# is the cheapest reliability win and matches `picotool`'s own design assumptions.
PICO_FLASH_RETRIES="${CEDE_HW_SMOKE_PICO_FLASH_RETRIES:-2}"  # total attempts, e.g. 2 = 1 retry
PICO_FLASH_BACKOFF="${CEDE_HW_SMOKE_PICO_FLASH_BACKOFF:-5}"  # seconds between attempts

t0=$(date +%s)
fails=0
checks=0
logdir="$(mktemp -d -t cede-hw-smoke-XXXXXX)"
trap 'rm -rf "$logdir"' EXIT

elapsed_since() {
  local s="$1" now
  now=$(date +%s)
  echo $(( now - s ))
}

# check <name> <timeout-secs> <expected-regex> <cmd...>
check() {
  local name="$1" tmo="$2" want="$3"
  shift 3
  local s log rc
  s=$(date +%s)
  log="$logdir/${name//[^A-Za-z0-9_-]/_}.log"
  checks=$(( checks + 1 ))
  timeout --foreground "$tmo" "$@" >"$log" 2>&1
  rc=$?
  if [ $rc -eq 0 ] && grep -qE -- "$want" "$log"; then
    printf '[%-22s] PASS (%2ss)\n' "$name" "$(elapsed_since "$s")"
    return 0
  fi
  if [ $rc -eq 124 ]; then
    printf '[%-22s] FAIL (%2ss)  timeout after %ss  see %s\n' \
      "$name" "$(elapsed_since "$s")" "$tmo" "$log"
  elif [ $rc -ne 0 ]; then
    printf '[%-22s] FAIL (%2ss)  command exit %d  see %s\n' \
      "$name" "$(elapsed_since "$s")" "$rc" "$log"
  else
    printf '[%-22s] FAIL (%2ss)  expected match: %q  see %s\n' \
      "$name" "$(elapsed_since "$s")" "$want" "$log"
  fi
  tail -n 8 "$log" | sed 's/^/    /'
  fails=$(( fails + 1 ))
  return 1
}

# check_with_retry <name> <attempts> <backoff-secs> <timeout-secs> <expected-regex> <cmd...>
#
# Same contract as `check`, but runs the command up to <attempts> times with
# <backoff> seconds between attempts. Counts as a single check; PASS as soon as
# any attempt matches. Each attempt's stdout/stderr is preserved in
# $logdir/<name>.attempt<N>.log so the operator can compare runs.
check_with_retry() {
  local name="$1" attempts="$2" backoff="$3" tmo="$4" want="$5"
  shift 5
  local i s log rc total_s
  total_s=$(date +%s)
  checks=$(( checks + 1 ))
  for (( i=1; i<=attempts; i++ )); do
    s=$(date +%s)
    log="$logdir/${name//[^A-Za-z0-9_-]/_}.attempt${i}.log"
    timeout --foreground "$tmo" "$@" >"$log" 2>&1
    rc=$?
    if [ $rc -eq 0 ] && grep -qE -- "$want" "$log"; then
      if [ "$i" -eq 1 ]; then
        printf '[%-22s] PASS (%2ss)\n' "$name" "$(elapsed_since "$total_s")"
      else
        printf '[%-22s] PASS (%2ss)  recovered on attempt %d/%d\n' \
          "$name" "$(elapsed_since "$total_s")" "$i" "$attempts"
      fi
      return 0
    fi
    if [ "$i" -lt "$attempts" ]; then
      if [ $rc -eq 124 ]; then
        printf '[%-22s] RETRY %d/%d (%2ss)  timeout after %ss; sleeping %ss\n' \
          "$name" "$i" "$attempts" "$(elapsed_since "$s")" "$tmo" "$backoff"
      elif [ $rc -ne 0 ]; then
        printf '[%-22s] RETRY %d/%d (%2ss)  command exit %d; sleeping %ss\n' \
          "$name" "$i" "$attempts" "$(elapsed_since "$s")" "$rc" "$backoff"
      else
        printf '[%-22s] RETRY %d/%d (%2ss)  expected match: %q; sleeping %ss\n' \
          "$name" "$i" "$attempts" "$(elapsed_since "$s")" "$want" "$backoff"
      fi
      sleep "$backoff"
    fi
  done
  if [ $rc -eq 124 ]; then
    printf '[%-22s] FAIL (%2ss)  %d attempts, last timeout after %ss  see %s\n' \
      "$name" "$(elapsed_since "$total_s")" "$attempts" "$tmo" "$log"
  elif [ $rc -ne 0 ]; then
    printf '[%-22s] FAIL (%2ss)  %d attempts, last exit %d  see %s\n' \
      "$name" "$(elapsed_since "$total_s")" "$attempts" "$rc" "$log"
  else
    printf '[%-22s] FAIL (%2ss)  %d attempts, expected match: %q  see %s\n' \
      "$name" "$(elapsed_since "$total_s")" "$attempts" "$want" "$log"
  fi
  tail -n 8 "$log" | sed 's/^/    /'
  fails=$(( fails + 1 ))
  return 1
}

# check_rc <name> <timeout-secs> <cmd...>  — pass iff exit status 0 (no log grep).
check_rc() {
  local name="$1" tmo="$2"
  shift 2
  local s log rc
  s=$(date +%s)
  log="$logdir/${name//[^A-Za-z0-9_-]/_}.log"
  checks=$(( checks + 1 ))
  timeout --foreground "$tmo" "$@" >"$log" 2>&1
  rc=$?
  if [ $rc -eq 0 ]; then
    printf '[%-22s] PASS (%2ss)\n' "$name" "$(elapsed_since "$s")"
    return 0
  fi
  if [ $rc -eq 124 ]; then
    printf '[%-22s] FAIL (%2ss)  timeout after %ss  see %s\n' \
      "$name" "$(elapsed_since "$s")" "$tmo" "$log"
  else
    printf '[%-22s] FAIL (%2ss)  command exit %d  see %s\n' \
      "$name" "$(elapsed_since "$s")" "$rc" "$log"
  fi
  tail -n 12 "$log" | sed 's/^/    /'
  fails=$(( fails + 1 ))
  return 1
}

printf '== cede hw-smoke (digest=%s, gateway=%s) ==\n' "$CEDE_IMAGE_ID" "$GATEWAY"

# 1–2. Tooling (Docker + cede) — builds run next; UF2/HEX need not exist beforehand.
check docker-version   "$STEP_TIMEOUT"  'Client:' docker version
check preflight        "$STEP_TIMEOUT"  'cede' uv run cede --help

# 3. Fresh hello_lab artifacts on Dev-Host (digest embedded = $CEDE_IMAGE_ID for flash+validate match).
check_rc docker-hello-lab-build "$BUILD_TIMEOUT" \
  make --no-print-directory -C "$REPO_ROOT/lab/docker" pico-build uno-build

# 4. Gateway health
check gateway-health   "$STEP_TIMEOUT"  'health: ok' make pi-gateway-health

# 5. Port resolution (assert by-id path; absence of rfkill / Wi-Fi noise is implicit
# because the regex pins the prefix).
check port-pico        "$STEP_TIMEOUT"  '/dev/serial/by-id/usb-Raspberry_Pi_' make pi-gateway-resolve-port-pico
check port-uno         "$STEP_TIMEOUT"  '/dev/serial/by-id/usb-Arduino_'      make pi-gateway-resolve-port-uno

# 6. I2C health (both must answer 0xce)
check i2c-0x42-pico    "$STEP_TIMEOUT"  '0xce' ssh "${SSH_TIMEOUT_OPTS[@]}" "$GATEWAY" 'sudo i2cget -y 1 0x42 0 b'
check i2c-0x43-uno     "$STEP_TIMEOUT"  '0xce' ssh "${SSH_TIMEOUT_OPTS[@]}" "$GATEWAY" 'sudo i2cget -y 1 0x43 0 b'

# 7. Pico flash + attest. Bounded retry-with-backoff: USB hubs (especially on Pi)
# occasionally drop a reset/enumerate cycle, and a single retry usually clears it.
check_with_retry pico-flash-test "$PICO_FLASH_RETRIES" "$PICO_FLASH_BACKOFF" \
  "$FLASH_TIMEOUT" "digest=$CEDE_IMAGE_ID" \
  make pi-gateway-flash-test-pico SKIP_SYNC=1 PICO_WAIT_MOUNT="$PICO_WAIT_MOUNT"

# 8. SSH argument-quoting probe after Pico flash (digest on wire matches fresh image).
check quote-probe      "$STEP_TIMEOUT"  'validate: ok' \
  env SKIP_SYNC=1 PICO_VALIDATE_WAIT=3 \
    bash gateway/scripts/devhost_pi_gateway.sh validate-pico-serial \
      --expect 'CEDE hello_lab rp2 ok' \
      --digest "$CEDE_IMAGE_ID"

# 9. Uno flash + attest
check uno-flash-test   "$FLASH_TIMEOUT" "digest=$CEDE_IMAGE_ID" \
  make pi-gateway-flash-test-uno SKIP_SYNC=1

elapsed=$(( $(date +%s) - t0 ))
if [ "$fails" -eq 0 ]; then
  printf '[%-22s] PASS  %ss  (%d/%d checks)\n' "hw-smoke" "$elapsed" "$checks" "$checks"
  exit 0
fi

# Failure path: keep the log dir for inspection.
trap - EXIT
printf '[%-22s] FAIL  %ss  (%d failure(s); logs preserved in %s)\n' \
  "hw-smoke" "$elapsed" "$fails" "$logdir"
exit 1
