#!/bin/bash
# Open 小揽 voice assistant UI (Chromium app window on http://127.0.0.1:8766).
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
UI_DIR="${AGENT_ROOT}/ui"
PORT="${AGENT_GUI_PORT:-8766}"
PIDFILE="${AGENT_ROOT}/run/gui_http.pid"
LOG="${AGENT_ROOT}/logs/gui_http.log"
GUI_LOG="${AGENT_ROOT}/logs/gui_autostart.log"
URL="http://127.0.0.1:${PORT}/"
CHROMIUM_PROFILE="${AGENT_ROOT}/run/chromium-kiosk"
USER_NAME="${USER:-youyeetoo}"

log() {
  echo "[gui] $*" | tee -a "${GUI_LOG}" >&2
}

notify() {
  log "$1"
  if command -v notify-send >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
    notify-send "小揽语音助手" "$1" 2>/dev/null || true
  fi
}

mkdir -p "${AGENT_ROOT}/run" "${AGENT_ROOT}/logs" "${CHROMIUM_PROFILE}"

LOCKFILE="${AGENT_ROOT}/run/gui.launch.lock"
exec 9>"${LOCKFILE}"
if ! flock -n 9; then
  log "another GUI launch in progress — skip"
  exit 0
fi

stop_existing_gui() {
  pkill -u "${USER_NAME}" -f "${CHROMIUM_PROFILE}" 2>/dev/null || true
  pkill -u "${USER_NAME}" -f "chromium.*${PORT}" 2>/dev/null || true
  sleep 0.5
}

port_listening() {
  python3 - <<PY
import socket
s = socket.socket()
try:
    s.settimeout(0.5)
    s.connect(("127.0.0.1", ${PORT}))
    print("yes")
except OSError:
    print("no")
finally:
    s.close()
PY
}

wait_ui_ready() {
  for _ in $(seq 1 30); do
    if python3 - <<PY 2>/dev/null
import urllib.request
html = urllib.request.urlopen("http://127.0.0.1:${PORT}/", timeout=1).read().decode("utf-8", "replace")
raise SystemExit(0 if "语音助手" in html else 1)
PY
    then
      log "UI HTTP ready"
      return 0
    fi
    sleep 0.2
  done
  notify "UI 页面未就绪，见 ${LOG}"
  return 1
}

start_http() {
  if [[ "$(port_listening)" == "yes" ]]; then
    return 0
  fi
  if [[ -f "${PIDFILE}" ]]; then
    old_pid="$(cat "${PIDFILE}")"
    if kill -0 "${old_pid}" 2>/dev/null; then
      kill "${old_pid}" 2>/dev/null || true
      sleep 0.2
    fi
    rm -f "${PIDFILE}"
  fi
  nohup python3 -m http.server "${PORT}" --bind 127.0.0.1 --directory "${UI_DIR}" >>"${LOG}" 2>&1 &
  echo $! >"${PIDFILE}"
  wait_ui_ready
}

hide_gnome_chrome() {
  export DISPLAY="${DISPLAY:-:0}"
  export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u "${USER_NAME}")/bus}"
  gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    "Main.panel.actor.hide(); 'ok'" 2>/dev/null || true
}

show_gnome_chrome() {
  export DISPLAY="${DISPLAY:-:0}"
  export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u "${USER_NAME}")/bus}"
  gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    "Main.panel.actor.show(); 'ok'" 2>/dev/null || true
}

chromium_running() {
  pgrep -u "${USER_NAME}" -f "${CHROMIUM_PROFILE}" >/dev/null 2>&1 \
    || pgrep -u "${USER_NAME}" -f "chromium.*${PORT}" >/dev/null 2>&1
}

open_browser() {
  local launcher="${AGENT_ROOT}/scripts/chromium_kiosk.sh"
  local flags=(
    --user-data-dir="${CHROMIUM_PROFILE}"
    --app="${URL}"
    --start-fullscreen
    --no-first-run
    --disable-infobars
    --disable-session-crashed-bubble
    --disable-translate
    --noerrdialogs
    --disable-restore-session-state
    --no-default-browser-check
    --disable-features=TranslateUI
    --class=XiaoLanVoice
  )
  if [[ -x "${launcher}" ]]; then
    /bin/bash "${launcher}" "${flags[@]}" >>"${GUI_LOG}" 2>&1 &
    return 0
  fi
  if [[ -x /usr/bin/chromium ]]; then
    /usr/bin/chromium "${flags[@]}" --disable-gpu >>"${GUI_LOG}" 2>&1 &
    return 0
  fi
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser "${flags[@]}" >>"${GUI_LOG}" 2>&1 &
    return 0
  fi
  return 1
}

if [[ ! -f "${UI_DIR}/index.html" ]]; then
  notify "缺少界面文件，请重新部署 agent"
  exit 1
fi

stop_existing_gui

# Stale lock after crash/power loss causes Chromium abort + desktop notify popup.
if [[ -f "${CHROMIUM_PROFILE}/SingletonLock" ]]; then
  rm -f "${CHROMIUM_PROFILE}/SingletonLock" "${CHROMIUM_PROFILE}/SingletonCookie" "${CHROMIUM_PROFILE}/SingletonSocket" 2>/dev/null || true
  log "removed stale chromium profile lock"
fi

start_http

if open_browser; then
  for _ in $(seq 1 15); do
    if chromium_running; then
      hide_gnome_chrome
      log "opened ${URL} profile=${CHROMIUM_PROFILE}"
      exit 0
    fi
    sleep 0.4
  done
  show_gnome_chrome
  notify "浏览器启动失败，已恢复桌面顶栏，见 ${GUI_LOG}"
  exit 1
else
  show_gnome_chrome
  notify "未找到可用浏览器，请手动打开 ${URL}"
  exit 1
fi
