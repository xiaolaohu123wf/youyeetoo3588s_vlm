#!/bin/bash
# Start Phase B orchestrator (VAD + state machine) on board
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
PIDFILE="${AGENT_ROOT}/run/orchestrator.pid"
LOG="${AGENT_ROOT}/logs/orchestrator.log"
API_PORT="${AGENT_API_PORT:-8765}"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
AUDIO_PROFILE="${AGENT_AUDIO_PROFILE:-auto}"
_hw="${VOICE_ROOT:-/userdata/voice}/scripts"
case "${AUDIO_PROFILE}" in
  fy_sp701)
    source "${_hw}/fy_sp701_hw.sh" 2>/dev/null || true
    echo "[start] audio profile: fy_sp701 (forced)"
    ;;
  board)
    source "${_hw}/voice_hw_board.sh" 2>/dev/null || true
    echo "[start] audio profile: board (forced)"
    ;;
  auto|*)
    if lsusb 2>/dev/null | grep -qiE 'cafe:b20a|Timesintelli'; then
      source "${_hw}/fy_sp701_hw.sh" 2>/dev/null || true
      echo "[start] audio profile: auto → fy_sp701 USB detected"
    else
      source "${_hw}/voice_hw_board.sh" 2>/dev/null || true
      echo "[start] audio profile: auto → board ES8388"
    fi
    ;;
esac
# Agent live mic: gain 8 clips loud syllables (e.g. 笑); 6 is safer for close-talk.
export MIC_CAPTURE_GAIN="${AGENT_MIC_CAPTURE_GAIN:-6}"
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

mkdir -p "${AGENT_ROOT}/run" "${AGENT_ROOT}/logs"

if [[ -f "${PIDFILE}" ]]; then
  old_pid="$(cat "${PIDFILE}")"
  if kill -0 "${old_pid}" 2>/dev/null; then
    echo "[start] orchestrator already running pid=${old_pid}"
    exit 0
  fi
  echo "[start] stale pidfile (${old_pid}) — cleaning up"
  rm -f "${PIDFILE}"
fi

# Clean up any stale temp tts files from prior runs
rm -f /tmp/agent_tts_*.wav /tmp/tts_out*.wav 2>/dev/null || true

# Orphan from manual runs / crash (pidfile missing but process or port still held)
if pgrep -f "orchestrator.main" >/dev/null 2>&1; then
  echo "[start] stopping orphan orchestrator.main"
  pkill -f "orchestrator.main" 2>/dev/null || true
  sleep 0.5
fi
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${API_PORT}/tcp" 2>/dev/null || true
  sleep 0.3
fi

if [[ ! -S /tmp/r1-llm.sock ]]; then
  echo "[start] llm_daemon not running — starting..."
  bash "${AGENT_ROOT}/scripts/start_llm_daemon.sh" || true
fi

_run_orchestrator() {
  nohup python3 -m orchestrator.main \
    --config "${AGENT_ROOT}/config/agent.yaml" \
    --agent-root "${AGENT_ROOT}" \
    >>"${LOG}" 2>&1 &
  echo $!
}

if [[ "$(id -u)" -eq 0 ]]; then
  echo "[start] dropping to user youyeetoo (avoid TTS file permission issues)"
  new_pid="$(sudo -u youyeetoo bash -c "
    export AGENT_ROOT='${AGENT_ROOT}' PYTHONPATH='${PYTHONPATH}' LD_LIBRARY_PATH='${LD_LIBRARY_PATH}' MIC_CAPTURE_GAIN='${MIC_CAPTURE_GAIN}'
    cd '${AGENT_ROOT}'
    nohup python3 -m orchestrator.main --config '${AGENT_ROOT}/config/agent.yaml' --agent-root '${AGENT_ROOT}' >>'${LOG}' 2>&1 &
    echo \$!
  ")"
else
  new_pid="$(_run_orchestrator)"
fi
echo "${new_pid}" >"${PIDFILE}"
sleep 2
if kill -0 "${new_pid}" 2>/dev/null; then
  echo "[start] orchestrator pid=${new_pid} log=${LOG}"
  echo "[start] speak to mic (${AUDIO_PROFILE:-auto}); watch: tail -f ${LOG}"
else
  echo "[start] FAILED — process exited; tail ${LOG}" >&2
  rm -f "${PIDFILE}"
  tail -20 "${LOG}" >&2 || true
  exit 1
fi
