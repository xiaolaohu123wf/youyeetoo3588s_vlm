#!/bin/bash
# FY-SP701 V3 USB 阵列麦 + 5W 功放 · 独立于板载 ES8388 (P3.6)
# 手册: 16 kHz · 2MIC 线性阵列 · 硬件 AEC/ANC/AGC · USB 免驱
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=voice_env.sh
source "${SCRIPT_DIR}/voice_env.sh"
# shellcheck source=fy_sp701_detect.sh
source "${SCRIPT_DIR}/fy_sp701_detect.sh"

export MIC_ROUTE=fy_sp701_usb
export MIC_SOURCE=usb
export PLAYBACK_ROUTE=fy_sp701_usb
export VOICE_HW=fy_sp701

# FY-SP701 前端已做 AGC/降噪，软件增益保守
export RECORD_RATE=16000
export RECORD_CHANNELS=2
export RECORD_SEC="${RECORD_SEC:-5}"
export MIC_CAPTURE_GAIN=0
export MIC_GAIN_LOCK=1
export MIC_KEEP=0
export VOICE_RESTORE_MIC=0

# 播放：模块自带 8Ω 5W 功放，勿叠加大增益
export PLAYBACK_NORMALIZE=1
export PLAYBACK_GAIN=2.0
export PLAYBACK_TARGET_PEAK=22000
export PLAYBACK_MAX_GAIN=4.0
export PLAYBACK_RATE=16000
export PLAYBACK_CHANNELS=2
export PLAYBACK_MONO=stereo
export PLAYBACK_WARMUP_SEC=0.08
export PLAYBACK_LEAD_MS=60
export PLAYBACK_FADE_MS=8
export PLAYBACK_TRIM_MS=40
export PLAYBACK_BUFFER_US=100000
export REPLAY_MONITOR_GAIN=3.0

# ASR：USB 前端输出通常电平正常，软件 boost 阈值放低
export ASR_BOOST_MIN_PEAK=2000
export ASR_TARGET_PEAK=14000
export ASR_MAX_GAIN=8.0

echo "[HW] FY-SP701 V3 · ${FY_ALSA_DEVICE} · ${RECORD_RATE}Hz ch=${RECORD_CHANNELS}"
