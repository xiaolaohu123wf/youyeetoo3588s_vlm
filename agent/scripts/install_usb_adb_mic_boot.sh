#!/bin/bash
# Install adb + FY-SP701 coexistence fix (boot delay, profile patch, hotplug recover).
# Run on board as root: sudo bash /userdata/agent/scripts/install_usb_adb_mic_boot.sh
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
DROPIN_DIR="/etc/systemd/system/usbdevice.service.d"
DROPIN_FILE="${DROPIN_DIR}/delay-for-host-usb.conf"
USB_BOOT_DELAY_SEC="${USB_BOOT_DELAY_SEC:-20}"

echo "[install] adb + SP701 fix (profile + boot delay + hotplug recover)"

chmod +x "${AGENT_ROOT}/scripts/retry_usbdevice.sh"
chmod +x "${AGENT_ROOT}/scripts/recover_adb_after_sp701.sh"
chmod +x "${AGENT_ROOT}/scripts/adb_guard_loop.sh"
chmod +x "${AGENT_ROOT}/scripts/patch_alsactl_profile.sh"
chmod +x "${AGENT_ROOT}/scripts/apply_adb_sp701_fix_now.sh"

bash "${AGENT_ROOT}/scripts/patch_alsactl_profile.sh"

install -m 644 "${AGENT_ROOT}/systemd/r1-usbdevice-retry.service" /etc/systemd/system/
install -m 644 "${AGENT_ROOT}/systemd/r1-adb-sp701-recover.service" /etc/systemd/system/
install -m 644 "${AGENT_ROOT}/systemd/r1-adb-guard.service" /etc/systemd/system/
install -m 644 "${AGENT_ROOT}/systemd/99-r1-sp701-adb-recover.rules" /etc/udev/rules.d/

mkdir -p "${DROPIN_DIR}"
cat >"${DROPIN_FILE}" <<EOF
# R1 agent: host USB (FY-SP701) may enumerate before dwc3 adb gadget is ready.
[Service]
ExecStartPre=/bin/sleep ${USB_BOOT_DELAY_SEC}
EOF

udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --subsystem-match=usb 2>/dev/null || true

systemctl daemon-reload
systemctl enable r1-usbdevice-retry.service r1-adb-sp701-recover.service r1-adb-guard.service

adb_ready() {
  systemctl is-active --quiet usbdevice.service 2>/dev/null \
    && pgrep -x adbd >/dev/null 2>&1
}

if adb_ready; then
  echo "[install] usbdevice already active — skip restart (avoids adb drop)"
else
  systemctl restart usbdevice.service || true
fi
systemctl restart r1-usbdevice-retry.service || true
systemctl restart r1-adb-guard.service || true

echo ""
echo "[install] wiring:"
echo "  PC adb  -> R1 USB Type-A DEBUG port (gadget / adbd)"
echo "  SP701   -> R1 USB HOST port (must NOT be the debug port)"
echo "  profile: alsactl restore no longer kills usbdevice"
echo "  hotplug: udev -> r1-adb-sp701-recover.service"
echo "  boot delay=${USB_BOOT_DELAY_SEC}s + retry service"
echo ""
systemctl --no-pager status usbdevice.service --lines=3 || true
pgrep -a adbd || echo "adbd not running yet — wait 30s"
echo "log: ${AGENT_ROOT}/logs/adb_sp701_recover.log"
