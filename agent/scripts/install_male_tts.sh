#!/bin/bash
# Download vits-zh-hf-fanchen-wnj (Chinese male) for agent voice catalog
set -euo pipefail

VOICE_ROOT="${VOICE_ROOT:-/userdata/voice}"
WNJ_DIR="${VOICE_ROOT}/vits-zh-hf-fanchen-wnj"
URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-zh-hf-fanchen-wnj.tar.bz2"

echo "=== Install male TTS (vits-zh-hf-fanchen-wnj) ==="

if [ -f "${WNJ_DIR}/vits-zh-hf-fanchen-wnj.onnx" ]; then
  echo "[skip] already present: ${WNJ_DIR}"
  exit 0
fi

tmp="/tmp/vits-zh-hf-fanchen-wnj.tar.bz2"
echo "[1/2] download (~120MB)"
wget -O "${tmp}" "${URL}"
echo "[2/2] extract"
tar xf "${tmp}" -C "${VOICE_ROOT}"
rm -f "${tmp}"
ls -lh "${WNJ_DIR}/vits-zh-hf-fanchen-wnj.onnx"
echo "=== Male TTS ready ==="
