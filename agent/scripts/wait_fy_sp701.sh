#!/bin/bash
# Wait for FY-SP701 USB audio before orchestrator auto-picks board profile.
set -euo pipefail

TIMEOUT="${FY_SP701_WAIT_SEC:-45}"
LOG="${AGENT_ROOT:-/userdata/agent}/logs/wait_fy_sp701.log"

log() {
  echo "[wait-fy-sp701] $*" | tee -a "${LOG}"
}

mkdir -p "$(dirname "${LOG}")"

for sec in $(seq 1 "${TIMEOUT}"); do
  if lsusb 2>/dev/null | grep -qiE 'cafe:b20a|Timesintelli'; then
    if grep -E '^[[:space:]]*[1-9][0-9]*[[:space:]]+\[.*USB' /proc/asound/cards >/dev/null 2>&1; then
      card="$(grep -E '^[[:space:]]*[1-9][0-9]*[[:space:]]+\[.*USB' /proc/asound/cards | head -1 | sed -E 's/^[[:space:]]*([0-9]+).*/\1/')"
      log "detected card=${card} after ${sec}s"
      exit 0
    fi
  fi
  sleep 1
done

log "no FY-SP701 after ${TIMEOUT}s — board mic if unplugged"
exit 0
