#!/bin/bash
# Start WiFi AP (hotspot) via NetworkManager — PC connects for WebUI at http://<AP_IP>:8766
set -euo pipefail

IF="${WIFI_AP_IFACE:-wlP4p65s0}"
SSID="${WIFI_AP_SSID:-YouYeetoo-R1}"
PASS="${WIFI_AP_PASSWORD:-youyeetoo1}"
LOG="${WIFI_AP_LOG:-/userdata/agent/logs/wifi_ap.log}"

mkdir -p "$(dirname "${LOG}")"
log() { echo "[wifi-ap] $(date -Iseconds) $*" | tee -a "${LOG}"; }

if ! command -v nmcli >/dev/null 2>&1; then
  log "ERROR: nmcli not found (NetworkManager required)"
  exit 1
fi

nmcli radio wifi on || true
nmcli device set "${IF}" managed yes 2>/dev/null || true

if nmcli -t -f NAME connection show --active | grep -qx "R1-Hotspot"; then
  log "already active on ${IF}"
  exit 0
fi

# Drop stale NM hotspot profiles from manual tests
while read -r name; do
  [[ -z "${name}" ]] && continue
  if [[ "${name}" == Hotspot || "${name}" == R1-Hotspot ]]; then
    nmcli connection delete "${name}" 2>/dev/null || true
  fi
done < <(nmcli -t -f NAME connection show 2>/dev/null || true)

log "starting SSID=${SSID} if=${IF}"
if ! nmcli device wifi hotspot ifname "${IF}" ssid "${SSID}" password "${PASS}" con-name R1-Hotspot; then
  log "hotspot failed — retry after disconnect"
  nmcli device disconnect "${IF}" 2>/dev/null || true
  sleep 1
  nmcli device wifi hotspot ifname "${IF}" ssid "${SSID}" password "${PASS}" con-name R1-Hotspot
fi

nmcli connection modify R1-Hotspot connection.autoconnect yes 2>/dev/null || true
IP="$(nmcli -g IP4.ADDRESS device show "${IF}" 2>/dev/null | head -1 | cut -d/ -f1)"
log "AP up ip=${IP:-unknown} — WebUI http://${IP:-10.42.0.1}:8766/ WS :8765"
