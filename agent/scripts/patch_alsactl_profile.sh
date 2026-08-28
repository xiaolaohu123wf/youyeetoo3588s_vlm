#!/bin/bash
# SP701 adds USB ALSA card not in /etc/asound.state; alsactl restore fails and
# breaks /usr/bin/usbdevice (sources /etc/profile with sh -e).
set -euo pipefail

PROFILE=/etc/profile
MARKER="r1-agent: alsactl must not break usbdevice"

if grep -q "${MARKER}" "${PROFILE}" 2>/dev/null; then
  echo "[patch-alsactl] already patched"
  exit 0
fi

python3 - <<'PY'
from pathlib import Path
profile = Path("/etc/profile")
text = profile.read_text(encoding="utf-8")
old = "alsactl restore -f /etc/asound.state"
new = "alsactl restore -f /etc/asound.state 2>/dev/null || true  # r1-agent: alsactl must not break usbdevice"
if old not in text:
    raise SystemExit("expected alsactl line missing in /etc/profile")
if new in text:
    raise SystemExit(0)
profile.write_text(text.replace(old, new, 1), encoding="utf-8")
print("[patch-alsactl] patched /etc/profile")
PY

grep alsactl "${PROFILE}"
