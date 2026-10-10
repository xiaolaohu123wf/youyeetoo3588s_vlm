#!/bin/bash
# Restore adb gadget after FY-SP701 hotplug. Avoid fighting boot-delayed usbdevice.
set -uo pipefail

LOG="${AGENT_ROOT:-/userdata/agent}/logs/adb_sp701_recover.log"
LOCK="${AGENT_ROOT:-/userdata/agent}/run/adb_recover.lock"
WAIT_SEC="${SP701_RECOVER_WAIT_SEC:-12}"
BOOT_GRACE_SEC="${ADB_BOOT_GRACE_SEC:-90}"
MAX_TRIES="${ADB_RECOVER_TRIES:-5}"

mkdir -p "$(dirname "${LOG}")" "$(dirname "${LOCK}")"

log() {
  echo "[adb-recover] $(date -Is) $*" | tee -a "${LOG}"
}

adb_ready() {
  systemctl is-active --quiet usbdevice.service 2>/dev/null \
    && pgrep -x adbd >/dev/null 2>&1
}

reset_gadget_udc() {
  local g="/sys/kernel/config/usb_gadget/rockchip"
  [ -f "${g}/UDC" ] || return 0
  echo "" >"${g}/UDC" 2>/dev/null || true
  sleep 2
}

recover_once() {
  systemctl reset-failed usbdevice.service 2>/dev/null || true
  reset_gadget_udc
  /usr/bin/usbdevice stop >>"${LOG}" 2>&1 || true
  sleep 2
  reset_gadget_udc
  if ! /usr/bin/usbdevice start >>"${LOG}" 2>&1; then
    systemctl restart usbdevice.service >>"${LOG}" 2>&1 || true
  fi
  sleep 3
  if ! pgrep -x adbd >/dev/null 2>&1 && command -v adbd >/dev/null 2>&1; then
    nohup adbd >>"${LOG}" 2>&1 &
    sleep 2
  fi
}

exec 9>"${LOCK}"
if ! flock -n 9; then
  log "another recover running — skip"
  exit 0
fi

log "triggered wait=${WAIT_SEC}s boot_grace=${BOOT_GRACE_SEC}s"
sleep "${WAIT_SEC}"

UPTIME="$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 999)"
if [ "${UPTIME}" -lt "${BOOT_GRACE_SEC}" ]; then
  extra=$((BOOT_GRACE_SEC - UPTIME))
  log "boot grace: wait extra ${extra}s (usbdevice has ExecStartPre sleep)"
  sleep "${extra}"
fi

if adb_ready; then
  log "ok already up adbd=$(pgrep -x adbd | tr '\n' ' ')"
  exit 0
fi

STATE="$(systemctl show usbdevice.service -p ActiveState --value 2>/dev/null || echo unknown)"
if [ "${STATE}" = "activating" ]; then
  log "usbdevice still activating — wait 30s before stop/start"
  sleep 30
  if adb_ready; then
    log "ok after activating wait adbd=$(pgrep -x adbd | tr '\n' ' ')"
    exit 0
  fi
fi

for try in $(seq 1 "${MAX_TRIES}"); do
  if adb_ready; then
    log "ok try=${try} adbd=$(pgrep -x adbd | tr '\n' ' ')"
    exit 0
  fi
  log "try=${try}/${MAX_TRIES} adb down — recover"
  recover_once
done

if adb_ready; then
  log "recovered adbd=$(pgrep -x adbd | tr '\n' ' ')"
  exit 0
fi

log "WARN: adb still down — tail ${LOG}; journalctl -u usbdevice -n 30"
exit 1
