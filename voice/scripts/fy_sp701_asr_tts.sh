#!/bin/bash
# FY-SP701: ASR → TTS loop (no LLM). P3.6 interactive acceptance.
set -euo pipefail
source /userdata/voice/scripts/fy_sp701_hw.sh

WAV="/tmp/fy_sp701_asr.wav"
MONO="/tmp/fy_sp701_asr_mono.wav"
SEC="${RECORD_SEC:-5}"

echo "[asr_tts] 滴——请说话 (${SEC}s)..."
bash /userdata/voice/scripts/fy_sp701_beep.sh 2>/dev/null || true
bash /userdata/voice/scripts/fy_sp701_record.sh "${WAV}" "${SEC}" "${RECORD_CHANNELS}"

if [ "${RECORD_CHANNELS}" -eq 2 ]; then
  python3 /userdata/voice/scripts/pick_mono.py "${WAV}" "${MONO}" >&2
else
  cp -f "${WAV}" "${MONO}"
fi

python3 /userdata/voice/scripts/analyze_wav.py "${MONO}" >&2
python3 /userdata/voice/scripts/prep_asr_wav.py "${MONO}" >&2 || true

ASR_RAW=$("${SHERPA_BIN}/sherpa-onnx-offline" \
  --tokens="${ASR_MODEL}/tokens.txt" \
  --sense-voice-model="${ASR_MODEL}/model.int8.onnx" \
  --sense-voice-language=zh \
  --num-threads=2 \
  "${MONO}" 2>&1) || true
TEXT=$(echo "${ASR_RAW}" | python3 /userdata/voice/scripts/asr_parse.py 2>/dev/null) || true

if [ -z "${TEXT}" ]; then
  echo "[asr_tts] ASR 失败" >&2
  exit 1
fi
echo "[asr_tts] 识别: ${TEXT}"

OUT="/tmp/fy_sp701_tts.wav"
echo "[asr_tts] TTS 合成..."
"${SHERPA_BIN}/sherpa-onnx-offline-tts" \
  --vits-model="${TTS_MODEL}/model.onnx" \
  --vits-tokens="${TTS_MODEL}/tokens.txt" \
  --vits-lexicon="${TTS_MODEL}/lexicon.txt" \
  --vits-dict-dir="${TTS_MODEL}/dict" \
  --sid=0 \
  --num-threads=2 \
  --output-filename="${OUT}" \
  "${TEXT}" >/dev/null

echo "[asr_tts] 模块喇叭播放（播完前勿 Ctrl+C）..."
bash /userdata/voice/scripts/fy_sp701_play.sh "${OUT}"
echo "[asr_tts] 完成"
