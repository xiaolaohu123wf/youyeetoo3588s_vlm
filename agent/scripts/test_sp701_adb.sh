#!/bin/bash
# Smoke test: SP701 hotplug should not permanently kill adb.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
LOG="${AGENT_ROOT}/logs/sp701_adb_test.log"

log() {
  echo "[sp701-test] $*" | tee -a "${LOG}"
}

adb_ready() {
  systemctl is-active --quiet usbdevice.service 2>/dev/null \
    && pgrep -x adbd >/dev/null 2>&1
}

log "=== SP701 adb test $(date -Is) ==="
log "lsusb before: $(lsusb | tr '\n' ';')"

if lsusb | grep -qiE 'cafe:b20a|Timesintelli'; then
  log "SP701 already plugged"
else
  log "SP701 not visible — plug into HOST port now, waiting up to 120s..."
  for _ in $(seq 1 120); do
    lsusb | grep -qiE 'cafe:b20a|Timesintelli' && break
    sleep 1
  done
fi

if ! lsusb | grep -qiE 'cafe:b20a|Timesintelli'; then
  log "FAIL: SP701 not detected"
  exit 1
fi
log "SP701 detected"

sleep 8

if adb_ready; then
  log "PASS: adb gadget up after SP701 (adbd=$(pgrep -x adbd | tr '\n' ' '))"
  exit 0
fi

log "adb down — running recover script"
bash "${AGENT_ROOT}/scripts/recover_adb_after_sp701.sh" || true
sleep 3

if adb_ready; then
  log "PASS: recovered after manual recover"
  exit 0
fi

log "FAIL: adb still down"
journalctl -u usbdevice -n 15 --no-pager >>"${LOG}" 2>&1 || true
exit 1
