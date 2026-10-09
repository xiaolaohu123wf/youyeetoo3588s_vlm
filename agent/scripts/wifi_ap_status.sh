#!/bin/bash
set -euo pipefail
IF="${WIFI_AP_IFACE:-wlP4p65s0}"
SSID="${WIFI_AP_SSID:-YouYeetoo-R1}"
IP="$(nmcli -g IP4.ADDRESS device show "${IF}" 2>/dev/null | head -1 | cut -d/ -f1)"
echo "=== R1 WiFi AP ==="
echo "SSID:     ${SSID}"
echo "IF:       ${IF}"
echo "AP IP:    ${IP:-<not up>}"
echo "WebUI:    http://${IP:-10.42.0.1}:8766/"
echo "WebSocket ws://${IP:-10.42.0.1}:8765/ws"
