#!/bin/bash
# One-shot fix on serial (no PC adb needed). Run as root on R1.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"

echo "[apply-now] SP701 + adb fix"

bash "${AGENT_ROOT}/scripts/patch_alsactl_profile.sh" 2>/dev/null || true
bash "${AGENT_ROOT}/scripts/install_usb_adb_mic_boot.sh"

echo "[apply-now] waiting for SP701 ALSA settle..."
sleep 5

if lsusb | grep -qiE 'cafe:b20a|Timesintelli'; then
  echo "[apply-now] SP701 detected — recover adb"
  SP701_RECOVER_WAIT_SEC=10 ADB_RECOVER_TRIES=6 \
    bash "${AGENT_ROOT}/scripts/recover_adb_after_sp701.sh" || true
else
  echo "[apply-now] SP701 not plugged — restart usbdevice only"
  systemctl reset-failed usbdevice.service 2>/dev/null || true
  systemctl restart usbdevice.service || true
fi

systemctl enable r1-adb-guard.service 2>/dev/null || true
systemctl restart r1-adb-guard.service 2>/dev/null || true

echo ""
pgrep -a adbd || echo "adbd NOT running"
systemctl is-active usbdevice || true
echo "PC: adb devices"
echo "log: ${AGENT_ROOT}/logs/adb_sp701_recover.log"
