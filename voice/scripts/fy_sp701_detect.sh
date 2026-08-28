#!/bin/bash
# Auto-detect FY-SP701 V3 USB audio (Timesintelli cafe:b20a) ALSA card index.
set -euo pipefail

find_fy_sp701_card() {
  local line idx rest name

  # Prefer USB id seen on R1: cafe:b20a Timesintelli USB Audio Device
  if lsusb 2>/dev/null | grep -qiE 'cafe:b20a|Timesintelli'; then
    while IFS= read -r line; do
      idx="${line%%[*}"
      idx="${idx// /}"
      rest="${line#*[}"
      name="${rest%%]*}"
      if echo "${name} ${line}" | grep -qiE 'USB|Device|Timesintelli|Audio'; then
        if [ "${idx}" != "0" ]; then
          echo "${idx}"
          return 0
        fi
      fi
    done < /proc/asound/cards
  fi

  # Fallback: any non-zero USB-Audio capture card
  while IFS= read -r line; do
    idx="${line%%[*}"
    idx="${idx// /}"
    rest="${line#*[}"
    name="${rest%%]*}"
    case "${name} ${line}" in
      *USB*Audio*|*USB*Device*)
        if [ "${idx}" != "0" ]; then
          echo "${idx}"
          return 0
        fi
        ;;
    esac
  done < /proc/asound/cards

  return 1
}

FY_ALSA_CARD="$(find_fy_sp701_card || true)"
if [ -z "${FY_ALSA_CARD}" ]; then
  echo "[FY-SP701] 未找到 USB 音频卡 (请确认 FY-SP701 已插入)" >&2
  echo "[FY-SP701] lsusb:" >&2
  lsusb 2>/dev/null | grep -iE 'audio|cafe|Timesintelli' >&2 || lsusb >&2
  echo "[FY-SP701] /proc/asound/cards:" >&2
  cat /proc/asound/cards >&2
  exit 1
fi

export FY_ALSA_CARD
export FY_ALSA_DEVICE="plughw:${FY_ALSA_CARD},0"
export ALSA_DEVICE="${FY_ALSA_DEVICE}"

echo "[FY-SP701] card=${FY_ALSA_CARD} device=${FY_ALSA_DEVICE}"
