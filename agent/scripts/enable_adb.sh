#!/bin/bash
# Enable Rockchip USB adb on fresh R1 flash (run on board as root)
set -euo pipefail

echo "[enable-adb] start"

if systemctl list-unit-files | grep -q usbdevice.service; then
  systemctl enable usbdevice.service 2>/dev/null || true
  systemctl restart usbdevice.service 2>/dev/null || true
  systemctl status usbdevice.service --no-pager -l || true
fi

if command -v adbd >/dev/null 2>&1; then
  pkill adbd 2>/dev/null || true
  nohup adbd >/tmp/adbd.log 2>&1 &
  sleep 1
  pgrep -a adbd || true
fi

echo "[enable-adb] USB devices:"
lsusb | grep -E '2207|Rockchip|Android' || lsusb

echo "[enable-adb] done — on PC: install RK USB driver, plug Type-A debug port, run: adb devices"
