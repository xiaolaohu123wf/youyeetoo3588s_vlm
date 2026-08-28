#!/bin/bash
# Keep adb up while FY-SP701 is on host USB (poll; safe after boot grace).
set -uo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
INTERVAL="${ADB_GUARD_INTERVAL_SEC:-8}"
BOOT_GRACE_SEC="${ADB_BOOT_GRACE_SEC:-90}"
LOG="${AGENT_ROOT}/logs/adb_guard.log"

log() {
  echo "[adb-guard] $(date -Is) $*" >>"${LOG}"
}

sp701_present() {
  lsusb 2>/dev/null | grep -qiE 'cafe:b20a|Timesintelli'
}

adb_ok() {
  systemctl is-active --quiet usbdevice.service 2>/dev/null \
    && pgrep -x adbd >/dev/null 2>&1
}

log "start interval=${INTERVAL}s boot_grace=${BOOT_GRACE_SEC}s"

while true; do
  UPTIME="$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 999)"
  if sp701_present && [ "${UPTIME}" -ge "${BOOT_GRACE_SEC}" ]; then
    if ! adb_ok; then
      log "adb down with SP701 — recover"
      SP701_RECOVER_WAIT_SEC=8 ADB_RECOVER_TRIES=4 \
        bash "${AGENT_ROOT}/scripts/recover_adb_after_sp701.sh" >>"${LOG}" 2>&1 || true
    fi
  fi
  sleep "${INTERVAL}"
done
