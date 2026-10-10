#!/bin/bash
# Launch Chromium for kiosk GUI — bypass /usr/bin/chromium wrapper EGL flags that
# conflict with --disable-gpu and crash when swiftshader is missing on R1.
set -euo pipefail

HERE="/usr/lib/chromium"
export LD_LIBRARY_PATH="${HERE}:${HERE}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export GNOME_DISABLE_CRASH_DIALOG=SET_BY_GOOGLE_CHROME

exec "${HERE}/chromium-bin" \
  --no-sandbox \
  --disable-gpu \
  --disable-gpu-compositing \
  --disable-dev-shm-usage \
  --single-process \
  "$@"
