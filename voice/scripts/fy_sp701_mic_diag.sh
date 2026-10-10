#!/bin/bash
# FY-SP701 mic diag: record → analyze → monitor replay → ASR
set -euo pipefail
source /userdata/voice/scripts/fy_sp701_hw.sh

SEC="${1:-5}"
WAV="/tmp/fy_sp701_mic_diag.wav"
MONO="/tmp/fy_sp701_mic_diag_mono.wav"

echo
echo "[DIAG] 滴——请对着 FY-SP701 阵列麦说话 (${SEC}s)..."
bash /userdata/voice/scripts/fy_sp701_beep.sh 2>/dev/null || true
bash /userdata/voice/scripts/fy_sp701_record.sh "${WAV}" "${SEC}" "${RECORD_CHANNELS}"

echo "[DIAG] 立体声分析:"
python3 /userdata/voice/scripts/analyze_stereo_wav.py "${WAV}" 2>/dev/null || python3 /userdata/voice/scripts/analyze_wav.py "${WAV}"

if [ "${RECORD_CHANNELS}" -eq 2 ]; then
  python3 /userdata/voice/scripts/pick_mono.py "${WAV}" "${MONO}" 2>&1 | sed 's/^/[DIAG] /'
else
  cp -f "${WAV}" "${MONO}"
fi

python3 /userdata/voice/scripts/analyze_wav.py "${MONO}"

echo
echo "[DIAG] ▶ 回放 (monitor)..."
bash /userdata/voice/scripts/fy_sp701_play.sh "${MONO}" monitor

echo
echo "[DIAG] ASR:"
python3 /userdata/voice/scripts/prep_asr_wav.py "${MONO}" 2>&1 | sed 's/^/[DIAG] /' || true
RAW=$("${SHERPA_BIN}/sherpa-onnx-offline" \
  --tokens="${ASR_MODEL}/tokens.txt" \
  --sense-voice-model="${ASR_MODEL}/model.int8.onnx" \
  --sense-voice-language=zh \
  --num-threads=2 \
  "${MONO}" 2>&1 | grep '"text"' | tail -1 || true)
echo "  ${RAW:-<empty>}"
TEXT=$(echo "${RAW}" | python3 /userdata/voice/scripts/asr_parse.py 2>/dev/null || true)
echo "[DIAG] 识别: ${TEXT:-<空>}"
