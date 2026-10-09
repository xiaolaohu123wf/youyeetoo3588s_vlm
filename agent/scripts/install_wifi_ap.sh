#!/bin/bash
# Install WiFi AP hotspot for PC WebUI access (run on board as root).
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
UNIT="${AGENT_ROOT}/systemd/r1-wifi-ap.service"

chmod +x "${AGENT_ROOT}/scripts/wifi_ap_start.sh" "${AGENT_ROOT}/scripts/wifi_ap_stop.sh"
install -m 644 "${UNIT}" /etc/systemd/system/r1-wifi-ap.service
systemctl daemon-reload
systemctl enable r1-wifi-ap.service
systemctl restart r1-wifi-ap.service || systemctl start r1-wifi-ap.service

echo "[install-wifi-ap] status:"
systemctl --no-pager status r1-wifi-ap.service --lines=5 || true
bash "${AGENT_ROOT}/scripts/wifi_ap_status.sh" || true
