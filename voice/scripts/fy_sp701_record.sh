#!/bin/bash
# Record via FY-SP701 USB device (no ES8388 routing).
set -euo pipefail
source /userdata/voice/scripts/fy_sp701_hw.sh

OUT="${1:?usage: fy_sp701_record.sh out.wav [seconds] [channels]}"
SEC="${2:-${RECORD_SEC:-5}}"
CH="${3:-${RECORD_CHANNELS:-2}}"

echo "[FY rec] ${SEC}s ch=${CH} → ${OUT}" >&2
AREC=(arecord -q -D "${ALSA_DEVICE}" -f S16_LE -r "${RECORD_RATE}" -c "${CH}" -d "${SEC}" "${OUT}")

if command -v pasuspender >/dev/null 2>&1; then
  pasuspender -- "${AREC[@]}" || "${AREC[@]}"
else
  "${AREC[@]}" || {
    echo "[FY rec] busy — retry in 0.5s" >&2
    sleep 0.5
    "${AREC[@]}"
  }
fi
echo "[FY rec] done" >&2
