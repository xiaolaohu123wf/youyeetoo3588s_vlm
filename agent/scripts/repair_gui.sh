#!/bin/bash
# One-shot repair when 小揽 GUI window is missing after reboot.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
USER_NAME="${AGENT_USER:-youyeetoo}"
LOG="${AGENT_ROOT}/logs/repair_gui.log"

log() {
  echo "[repair-gui] $*" | tee -a "${LOG}"
}

mkdir -p "${AGENT_ROOT}/logs"

log "=== repair GUI $(date -Is) ==="

export DISPLAY="${DISPLAY:-:0}"

# Restore GNOME top bar if a prior failed launch hid it.
if command -v gdbus >/dev/null 2>&1; then
  gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    "Main.panel.actor.show(); 'ok'" 2>/dev/null || true
fi

# Prefer HDMI if a phantom DSI confuses the session.
if [[ -x "${AGENT_ROOT}/scripts/display_hdmi_only.sh" ]]; then
  bash "${AGENT_ROOT}/scripts/display_hdmi_only.sh" >>"${LOG}" 2>&1 || true
fi

# Backend services
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart r1-llm-daemon.service 2>>"${LOG}" || true
  sleep 2
  systemctl restart r1-orchestrator.service 2>>"${LOG}" || true
else
  bash "${AGENT_ROOT}/scripts/start_llm_daemon.sh" >>"${LOG}" 2>&1 || true
  bash "${AGENT_ROOT}/scripts/start_orchestrator.sh" >>"${LOG}" 2>&1 || true
fi

sleep 3

# Reset stuck browser profile after crash / power loss.
CHROMIUM_PROFILE="${AGENT_ROOT}/run/chromium-kiosk"
if pgrep -u "${USER_NAME}" -f "${CHROMIUM_PROFILE}" >/dev/null 2>&1; then
  log "stopping old chromium"
  pkill -u "${USER_NAME}" -f "${CHROMIUM_PROFILE}" 2>/dev/null || true
  sleep 1
fi
if [[ -f "${CHROMIUM_PROFILE}/SingletonLock" ]]; then
  log "removing stale chromium SingletonLock"
  rm -f "${CHROMIUM_PROFILE}/SingletonLock" "${CHROMIUM_PROFILE}/SingletonCookie" "${CHROMIUM_PROFILE}/SingletonSocket" 2>/dev/null || true
fi

log "opening GUI (user=${USER_NAME})"
UID_NUM="$(id -u "${USER_NAME}" 2>/dev/null || echo 1000)"
if [[ "$(id -un)" == "${USER_NAME}" ]]; then
  exec /bin/bash "${AGENT_ROOT}/scripts/open_agent_gui.sh"
fi
exec sudo -u "${USER_NAME}" \
  DISPLAY="${DISPLAY:-:0}" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${UID_NUM}/bus" \
  /bin/bash "${AGENT_ROOT}/scripts/open_agent_gui.sh"
