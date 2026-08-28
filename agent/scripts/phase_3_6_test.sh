#!/bin/bash
# Phase 3.6 — FY-SP701 V3 USB 阵列麦 + 功放模组验收
# 用法:
#   bash /userdata/agent/scripts/phase_3_6_test.sh           # 全自动（含需说话的步骤会等待）
#   bash /userdata/agent/scripts/phase_3_6_test.sh --quick   # 跳过交互 ASR/TTS
#   bash /userdata/agent/scripts/phase_3_6_test.sh --live     # 末尾跑 fy_sp701_asr_tts 交互验收
set -euo pipefail

QUICK=0
LIVE=0
for arg in "$@"; do
  case "${arg}" in
    --quick) QUICK=1 ;;
    --live) LIVE=1 ;;
  esac
done

VOICE="/userdata/voice/scripts"
AGENT="${AGENT_ROOT:-/userdata/agent}"
RUN="/tmp/p36_$$"
mkdir -p "${RUN}"
trap 'rm -rf "${RUN}"' EXIT

pass=0
fail=0
skip=0

ok()   { echo "[PASS] $*"; pass=$((pass + 1)); }
bad()  { echo "[FAIL] $*"; fail=$((fail + 1)); }
note() { echo "[....] $*"; skip=$((skip + 1)); }

source "${VOICE}/voice_env.sh"
source "${VOICE}/fy_sp701_hw.sh"

# Release ALSA device (orchestrator / prior aplay may hold card 1)
pkill -f "orchestrator.main" 2>/dev/null || true
sleep 0.5

echo "=============================================="
echo " Phase 3.6 · FY-SP701 V3 USB 语音模组验收"
echo " device=${ALSA_DEVICE}  rate=${RECORD_RATE}Hz"
echo "=============================================="

# --- 1. USB 枚举 ---
echo ""
echo "[1/8] USB / ALSA 枚举"
if lsusb 2>/dev/null | grep -qiE 'cafe:b20a|Timesintelli|USB Audio'; then
  lsusb | grep -iE 'cafe:b20a|Timesintelli|USB Audio' || true
  ok "lsusb 可见 USB 音频设备"
else
  bad "lsusb 未找到 FY-SP701 (cafe:b20a / Timesintelli)"
fi

if aplay -l 2>/dev/null | grep -q "card ${FY_ALSA_CARD}:"; then
  aplay -l | grep -A1 "card ${FY_ALSA_CARD}:" || true
  ok "aplay card ${FY_ALSA_CARD} 播放端"
else
  bad "aplay 无 card ${FY_ALSA_CARD}"
fi

if arecord -l 2>/dev/null | grep -q "card ${FY_ALSA_CARD}:"; then
  arecord -l | grep -A1 "card ${FY_ALSA_CARD}:" || true
  ok "arecord card ${FY_ALSA_CARD} 采集端"
else
  bad "arecord 无 card ${FY_ALSA_CARD}"
fi

# --- 2. 播放测试（模块功放） ---
echo ""
echo "[2/8] 喇叭播放 · 880Hz 提示音"
TONE="${RUN}/tone.wav"
python3 - <<PY
import struct, math, wave
rate = 16000
with wave.open("${RUN}/tone.wav", "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    for freq, dur, amp in [(880, 0.35, 18000), (660, 0.35, 16000)]:
        for i in range(int(rate * dur)):
            v = int(amp * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", v))
PY
if bash "${VOICE}/fy_sp701_play.sh" "${TONE}"; then
  ok "USB 功放播放"
else
  bad "aplay 失败"
fi
sleep 0.4

# --- 3. 立体声采集（2MIC） ---
echo ""
echo "[3/8] 双麦立体声采集 (3s) — 请对着模组说话"
REC_ST="${RUN}/stereo.wav"
bash "${VOICE}/fy_sp701_beep.sh" 2>/dev/null || true
bash "${VOICE}/fy_sp701_record.sh" "${REC_ST}" 3 2
STEREO_LOG="${RUN}/stereo.log"
python3 "${VOICE}/analyze_stereo_wav.py" "${REC_ST}" | tee "${STEREO_LOG}"
if grep -q "VERDICT: STEREO_OK" "${STEREO_LOG}"; then
  ok "双麦均有信号"
elif grep -qE "VERDICT: (SOFT|STEREO|IMBALANCED)" "${STEREO_LOG}"; then
  ok "双麦有信号 (电平见上)"
else
  bad "双麦采集异常 — $(grep VERDICT "${STEREO_LOG}" || echo unknown)"
fi

MONO="${RUN}/mono.wav"
python3 "${VOICE}/pick_mono.py" "${REC_ST}" "${MONO}" >/dev/null 2>&1 || cp -f "${REC_ST}" "${MONO}"
ANALYZE=$(python3 "${VOICE}/analyze_wav.py" "${MONO}")
echo "${ANALYZE}"
if echo "${ANALYZE}" | grep -qE "VERDICT: (SIGNAL_OK|SOFT_OK|HOT)"; then
  ok "单声道电平可 ASR"
else
  bad "电平过低或静音"
fi

# --- 4. 16 kHz 规格 ---
echo ""
echo "[4/8] 采样率 16 kHz"
RATE=$(python3 - <<PY
import wave
with wave.open("${MONO}", "rb") as w:
    print(w.getframerate())
PY
)
if [ "${RATE}" = "16000" ]; then
  ok "采样率 ${RATE} Hz"
else
  bad "采样率 ${RATE} Hz (期望 16000)"
fi

# --- 5. AEC 粗测：播放时采集（保持安静） ---
echo ""
echo "[5/8] AEC 粗测 — 播放 tone 时录音 3s，请保持安静"
BASE="${RUN}/aec_base.wav"
ECHO="${RUN}/aec_echo.wav"
bash "${VOICE}/fy_sp701_record.sh" "${BASE}" 2 1
python3 - <<PY &
import struct, math, wave, time
rate = 16000
dur = 3.0
n = int(rate * dur)
path = "${RUN}/aec_tone.wav"
with wave.open(path, "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    for i in range(n):
        v = int(22000 * math.sin(2 * math.pi * 440 * i / rate))
        w.writeframes(struct.pack("<h", v))
time.sleep(0.15)
PY
sleep 0.2
if command -v pasuspender >/dev/null 2>&1; then
  pasuspender -- aplay -q -D "${ALSA_DEVICE}" "${RUN}/aec_tone.wav" &
else
  aplay -q -D "${ALSA_DEVICE}" "${RUN}/aec_tone.wav" &
fi
PLAY_PID=$!
sleep 0.25
bash "${VOICE}/fy_sp701_record.sh" "${ECHO}" 3 1
wait "${PLAY_PID}" 2>/dev/null || true

BASE_PEAK=$(python3 "${VOICE}/analyze_wav.py" "${BASE}" | sed -n 's/.*peak=\([0-9]*\).*/\1/p')
ECHO_PEAK=$(python3 "${VOICE}/analyze_wav.py" "${ECHO}" | sed -n 's/.*peak=\([0-9]*\).*/\1/p')
echo "  安静 baseline peak=${BASE_PEAK} · 播放中 peak=${ECHO_PEAK}"
if [ -n "${BASE_PEAK}" ] && [ -n "${ECHO_PEAK}" ]; then
  awk -v b="${BASE_PEAK}" -v e="${ECHO_PEAK}" 'BEGIN{
    if (b < 200 && e > 3000) { print "  → 检测到播放泄漏（硬件 AEC 可能未完全抑制）"; exit 0 }
    if (e <= b * 4 + 500) { print "  → 播放中 peak 未异常飙升（AEC/前端处理正常倾向）"; exit 0 }
    print "  → 播放中 peak 升高，属预期；全双工对话需实机验证"
    exit 0
  }'
  ok "AEC 粗测完成 (peak base=${BASE_PEAK} echo=${ECHO_PEAK})"
else
  bad "AEC 粗测无法读 peak"
fi

# --- 6. ASR smoke（文件） ---
echo ""
echo "[6/8] ASR smoke (SenseVoice · 上一步录音)"
python3 "${VOICE}/prep_asr_wav.py" "${MONO}" 2>&1 | sed 's/^/  /' || true
ASR_RAW=$("${SHERPA_BIN}/sherpa-onnx-offline" \
  --tokens="${ASR_MODEL}/tokens.txt" \
  --sense-voice-model="${ASR_MODEL}/model.int8.onnx" \
  --sense-voice-language=zh \
  --num-threads=2 \
  "${MONO}" 2>&1) || true
TEXT=$(echo "${ASR_RAW}" | python3 "${VOICE}/asr_parse.py" 2>/dev/null) || true
if [ -n "${TEXT}" ]; then
  echo "  ASR: ${TEXT}"
  ok "SenseVoice 识别成功"
else
  if [ "${QUICK}" = "1" ]; then
    note "ASR 空（--quick 模式，可能未说话）"
  else
    bad "ASR 未识别 — 请重跑并对着模组清晰说话"
  fi
fi

# --- 7. TTS → 模块喇叭 ---
echo ""
echo "[7/8] TTS → FY-SP701 喇叭"
TTS_OUT="${RUN}/tts.wav"
PHRASE="华芸模组播放测试，一二三四五。"
if "${SHERPA_BIN}/sherpa-onnx-offline-tts" \
  --vits-model="${TTS_MODEL}/model.onnx" \
  --vits-tokens="${TTS_MODEL}/tokens.txt" \
  --vits-lexicon="${TTS_MODEL}/lexicon.txt" \
  --vits-dict-dir="${TTS_MODEL}/dict" \
  --sid=0 --num-threads=2 \
  --output-filename="${TTS_OUT}" \
  "${PHRASE}" >/dev/null 2>&1; then
  bash "${VOICE}/fy_sp701_play.sh" "${TTS_OUT}"
  ok "TTS 经模块功放播放"
else
  bad "TTS 合成失败"
fi

# --- 8. 交互 E2E（可选） ---
echo ""
echo "[8/8] ASR→TTS 闭环"
if [ "${LIVE}" = "1" ]; then
  bash "${VOICE}/fy_sp701_asr_tts.sh" && ok "fy_sp701_asr_tts 交互验收" || bad "fy_sp701_asr_tts 失败"
elif [ "${QUICK}" = "1" ]; then
  note "跳过交互 (加 --live 运行: bash ${AGENT}/scripts/phase_3_6_test.sh --live)"
else
  echo "  手动验收: bash ${VOICE}/fy_sp701_asr_tts.sh"
  note "交互 ASR→TTS 留待手动 / --live"
fi

# --- Agent 集成提示 ---
echo ""
echo "----------------------------------------------"
echo " Agent 切换 FY-SP701 (capture + playback):"
echo "   export ALSA_CAPTURE_DEVICE=${ALSA_DEVICE}"
echo "   # agent.yaml vad.alsa_device → ${ALSA_DEVICE}"
echo "   # TTS 播放改用 fy_sp701_play.sh 或设 PLAYBACK_DEVICE"
echo "----------------------------------------------"

echo ""
echo "=============================================="
echo " Phase 3.6 结果: PASS=${pass} FAIL=${fail} SKIP=${skip}"
echo "=============================================="
[ "${fail}" -eq 0 ]
