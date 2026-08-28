#!/bin/bash
# Retry adb gadget after FY-SP701 (or other host USB) finishes enumerating at boot.
set -euo pipefail

LOG="${AGENT_ROOT:-/userdata/agent}/logs/usbdevice_retry.log"
mkdir -p "$(dirname "${LOG}")"

log() {
  echo "[usb-retry] $(date -Is) $*" | tee -a "${LOG}"
}

wait_sec="${USB_RETRY_WAIT_SEC:-15}"
max_tries="${USB_RETRY_MAX:-5}"

adb_ready() {
  systemctl is-active --quiet usbdevice.service 2>/dev/null \
    && pgrep -x adbd >/dev/null 2>&1
}

restart_usbdevice() {
  systemctl reset-failed usbdevice.service 2>/dev/null || true
  systemctl restart usbdevice.service 2>>"${LOG}" || true
  if ! adb_ready; then
    /usr/bin/usbdevice stop 2>>"${LOG}" || true
    sleep 1
    /usr/bin/usbdevice start 2>>"${LOG}" || true
  fi
  if ! pgrep -x adbd >/dev/null 2>&1 && command -v adbd >/dev/null 2>&1; then
    nohup adbd >>"${LOG}" 2>&1 &
    sleep 1
  fi
}

log "start wait=${wait_sec}s max_tries=${max_tries}"

if adb_ready; then
  log "ok already up adbd=$(pgrep -x adbd | tr '\n' ' ')"
  exit 0
fi

for try in $(seq 1 "${max_tries}"); do
  sleep "${wait_sec}"

  if adb_ready; then
    log "ok try=${try} usbdevice=active adbd=$(pgrep -x adbd | tr '\n' ' ')"
    exit 0
  fi

  reason="usbdevice not ready"
  if systemctl is-failed usbdevice.service >/dev/null 2>&1; then
    reason="usbdevice failed"
  elif ! pgrep -x adbd >/dev/null 2>&1; then
    reason="adbd missing"
  fi

  log "try=${try}/${max_tries} ${reason} -> restart usbdevice"
  restart_usbdevice
  sleep 2
done

if systemctl is-active usbdevice.service >/dev/null 2>&1 && pgrep -x adbd >/dev/null 2>&1; then
  log "ok after retries"
  exit 0
fi

log "WARN: adb gadget still not up — unplug FY-SP701, run: systemctl restart usbdevice.service"
exit 1
