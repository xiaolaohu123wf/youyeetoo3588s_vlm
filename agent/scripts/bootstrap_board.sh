#!/bin/bash
# Post-flash board bootstrap: voice stack + agent autostart + GUI
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
VOICE_ROOT="${VOICE_ROOT:-/userdata/voice}"
MODEL_DIR="${LLM_MODEL_DIR:-/userdata/models/InternVL3_5-4B}"
LOG="${AGENT_ROOT}/logs/bootstrap.log"

log() {
  echo "[bootstrap] $*" | tee -a "${LOG}"
}

mkdir -p "${AGENT_ROOT}/logs" "${AGENT_ROOT}/run" "${VOICE_ROOT}" /userdata/models

log "=== bootstrap $(date -Is) ==="

log "[1/7] sherpa runtime + VAD"
bash "${AGENT_ROOT}/scripts/install_sherpa_runtime.sh" 2>&1 | tee -a "${LOG}"

log "[2/7] streaming ASR model"
bash "${AGENT_ROOT}/scripts/install_streaming_asr.sh" 2>&1 | tee -a "${LOG}"

log "[3/7] Matcha TTS"
bash "${AGENT_ROOT}/scripts/install_matcha_tts.sh" 2>&1 | tee -a "${LOG}"

log "[4/7] optional male TTS (wnj)"
bash "${AGENT_ROOT}/scripts/install_male_tts.sh" 2>&1 | tee -a "${LOG}" || log "WARN: male TTS optional install failed"

log "[5/7] llm_daemon binary"
if [[ ! -x "${AGENT_ROOT}/bin/llm_daemon" ]]; then
  log "ERROR: missing ${AGENT_ROOT}/bin/llm_daemon — push from PC first"
  exit 1
fi
chmod +x "${AGENT_ROOT}/bin/llm_daemon"

if [[ ! -f "${MODEL_DIR}/llm_InternVL3_5-4B.rknn" ]]; then
  log "WARN: InternVL model missing at ${MODEL_DIR}"
  log "WARN: push from PC: adb push InternVL3_5-4B /userdata/models/"
else
  log "InternVL model present"
fi

log "[6/7] HDMI + desktop prep"
if [[ -x "${AGENT_ROOT}/scripts/display_hdmi_only.sh" ]]; then
  bash "${AGENT_ROOT}/scripts/display_hdmi_only.sh" 2>&1 | tee -a "${LOG}" || true
fi

log "[7/7] systemd + GUI autostart"
if [[ "$(id -u)" -eq 0 ]]; then
  bash "${AGENT_ROOT}/scripts/install_autostart.sh" 2>&1 | tee -a "${LOG}"
else
  sudo bash "${AGENT_ROOT}/scripts/install_autostart.sh" 2>&1 | tee -a "${LOG}"
fi

log "=== bootstrap done ==="
log "Verify: bash ${AGENT_ROOT}/scripts/phase_e_test.sh"
log "GUI: bash ${AGENT_ROOT}/scripts/open_agent_gui.sh"
