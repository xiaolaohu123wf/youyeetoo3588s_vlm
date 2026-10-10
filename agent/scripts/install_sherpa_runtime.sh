#!/bin/bash
# Sherpa-onnx aarch64 runtime + Silero VAD (fresh flash bootstrap)
set -euo pipefail

VOICE_ROOT="${VOICE_ROOT:-/userdata/voice}"
SHERPA_DIR="${VOICE_ROOT}/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu"
TARBALL_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.8/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu.tar.bz2"
VAD_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"

mkdir -p "${VOICE_ROOT}"

if [[ ! -x "${SHERPA_DIR}/bin/sherpa-onnx-offline" ]]; then
  echo "[sherpa] download runtime"
  tmp="/tmp/sherpa-onnx-aarch64.tar.bz2"
  wget -O "${tmp}" "${TARBALL_URL}"
  tar xf "${tmp}" -C "${VOICE_ROOT}"
  rm -f "${tmp}"
else
  echo "[sherpa] runtime already present"
fi

if [[ ! -f "${VOICE_ROOT}/silero_vad.onnx" ]]; then
  echo "[sherpa] download silero_vad.onnx"
  wget -O "${VOICE_ROOT}/silero_vad.onnx" "${VAD_URL}"
else
  echo "[sherpa] silero_vad already present"
fi

echo "[sherpa] ok: ${SHERPA_DIR}"
