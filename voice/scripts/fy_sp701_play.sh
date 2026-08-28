#!/bin/bash
# Play wav via FY-SP701 USB speaker (no ES8388 routing).
set -euo pipefail
WAV="${1:?usage: fy_sp701_play.sh file.wav [monitor]}"
MODE="${2:-}"

source /userdata/voice/scripts/fy_sp701_hw.sh

WARMUP="${PLAYBACK_WARMUP_SEC:-0.08}"
if awk "BEGIN{exit !(${WARMUP} > 0)}"; then
  sleep "${WARMUP}"
fi

PLAY=/tmp/fy_sp701_play.wav
CHANNELS="${PLAYBACK_CHANNELS:-2}"
export PLAYBACK_CHANNELS="${CHANNELS}"

if [ "${MODE}" = "monitor" ]; then
  PLAYBACK_MODE=monitor PLAYBACK_GAIN="${REPLAY_MONITOR_GAIN:-3.0}" \
    PLAYBACK_LEAD_MS="${PLAYBACK_LEAD_MS:-60}" \
    python3 /userdata/voice/scripts/wav_to_16k_mono.py "${WAV}" "${PLAY}" >&2
else
  python3 /userdata/voice/scripts/wav_to_16k_mono.py "${WAV}" "${PLAY}" >&2
fi

echo "[FY play] ▶ ${WAV} (${MODE:-normal}) on ${ALSA_DEVICE}" >&2
APLAY_OPTS=()
if [ -n "${PLAYBACK_BUFFER_US:-}" ]; then
  APLAY_OPTS+=(--buffer-time="${PLAYBACK_BUFFER_US}")
fi

if command -v pasuspender >/dev/null 2>&1; then
  pasuspender -- aplay -D "${ALSA_DEVICE}" "${APLAY_OPTS[@]}" "${PLAY}"
else
  aplay -D "${ALSA_DEVICE}" "${APLAY_OPTS[@]}" "${PLAY}"
fi
echo "[FY play] 完成" >&2
