#!/bin/bash
set -euo pipefail
IF="${WIFI_AP_IFACE:-wlP4p65s0}"
nmcli connection down R1-Hotspot 2>/dev/null || true
nmcli device disconnect "${IF}" 2>/dev/null || true
echo "[wifi-ap] stopped"
