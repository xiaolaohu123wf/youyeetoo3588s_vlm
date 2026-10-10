#!/bin/bash
# Install systemd autostart + desktop launcher for R1 voice agent.
# Run on board as root: sudo bash /userdata/agent/scripts/install_autostart.sh
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
USER_NAME="${AGENT_USER:-youyeetoo}"
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
DESKTOP_DIR="${USER_HOME}/Desktop"
APPS_DIR="${USER_HOME}/.local/share/applications"
AUTOSTART_DIR="${USER_HOME}/.config/autostart"

echo "[install] R1 agent autostart + desktop GUI"

install -d "${AGENT_ROOT}/ui" "${AGENT_ROOT}/systemd"
chmod +x "${AGENT_ROOT}/scripts/open_agent_gui.sh" 2>/dev/null || true
chmod +x "${AGENT_ROOT}/scripts/autostart_agent_gui.sh" 2>/dev/null || true
chmod +x "${AGENT_ROOT}/scripts/set_tech_wallpaper.sh" 2>/dev/null || true
chmod +x "${AGENT_ROOT}/scripts/display_hdmi_only.sh" 2>/dev/null || true

# systemd units
install -m 644 "${AGENT_ROOT}/systemd/r1-llm-daemon.service" /etc/systemd/system/
if [[ -f "${AGENT_ROOT}/systemd/r1-vlm-daemon.service" ]]; then
  install -m 644 "${AGENT_ROOT}/systemd/r1-vlm-daemon.service" /etc/systemd/system/
fi
install -m 644 "${AGENT_ROOT}/systemd/r1-orchestrator.service" /etc/systemd/system/
chmod +x "${AGENT_ROOT}/scripts/orchestrator_wait_infer_sock.sh" 2>/dev/null || true
chmod +x "${AGENT_ROOT}/scripts/wait_vlm_sock.sh" 2>/dev/null || true
if [[ -f "${AGENT_ROOT}/systemd/r1-webui.service" ]]; then
  install -m 644 "${AGENT_ROOT}/systemd/r1-webui.service" /etc/systemd/system/
fi
if [[ -f "${AGENT_ROOT}/systemd/r1-p4-eth.service" ]]; then
  install -m 644 "${AGENT_ROOT}/systemd/r1-p4-eth.service" /etc/systemd/system/
fi
systemctl daemon-reload

# adb shell + systemctl restart often hangs (D-state). Only start if inactive; skip restart if already running.
svc_start() {
  local u="$1"
  if systemctl is-active --quiet "$u" 2>/dev/null; then
    echo "[install] $u already active — skip restart (adb-safe)"
    return 0
  fi
  echo "[install] starting $u ..."
  timeout 30 systemctl start "$u" || echo "[install] WARN: start $u timed out — reboot if stuck" >&2
}

P4_ROOT="${P4_ROOT:-/userdata/p4}"
if systemctl list-unit-files r1-p4-eth.service >/dev/null 2>&1; then
  systemctl enable r1-p4-eth.service
  systemctl start r1-p4-eth.service || true
fi
# MediaMTX relay + frame cache (keeps mediamtx_latest.jpg fresh for vision / 重拍)
if [[ -x "${P4_ROOT}/bin/mediamtx" ]] && [[ -f "${P4_ROOT}/systemd/r1-mediamtx.service" ]]; then
  install -m 644 "${P4_ROOT}/systemd/r1-mediamtx.service" /etc/systemd/system/
  chmod +x "${P4_ROOT}/scripts/mediamtx_gen_config.sh" 2>/dev/null || true
  bash "${P4_ROOT}/scripts/mediamtx_gen_config.sh" 2>/dev/null || true
  systemctl enable r1-mediamtx.service
  svc_start r1-mediamtx.service
fi
if [[ -f "${AGENT_ROOT}/systemd/r1-mediamtx-frame.service" ]] && [[ -x "${P4_ROOT}/bin/mediamtx" ]]; then
  chmod +x "${AGENT_ROOT}/scripts/mediamtx_rtsp_frame_daemon.sh" 2>/dev/null || true
  sed -i 's/\r$//' "${AGENT_ROOT}/scripts/mediamtx_rtsp_frame_daemon.sh" 2>/dev/null || true
  install -m 644 "${AGENT_ROOT}/systemd/r1-mediamtx-frame.service" /etc/systemd/system/
  systemctl enable r1-mediamtx-frame.service
  svc_start r1-mediamtx-frame.service
fi
systemctl daemon-reload
USE_VLM=0
if systemctl list-unit-files r1-vlm-daemon.service >/dev/null 2>&1; then
  if [[ -x "${AGENT_ROOT}/bin/vlm_daemon" ]] && [[ -s "${AGENT_ROOT}/bin/vlm_daemon" ]]; then
    USE_VLM=1
    systemctl enable r1-vlm-daemon.service
    systemctl disable r1-llm-daemon.service 2>/dev/null || true
  fi
fi
if [[ "${USE_VLM}" -eq 0 ]]; then
  systemctl enable r1-llm-daemon.service
fi
systemctl enable r1-orchestrator.service
if systemctl list-unit-files r1-webui.service >/dev/null 2>&1; then
  systemctl enable r1-webui.service
fi

pkill -f 'xiaolan_cli serve' 2>/dev/null || true
pkill -f 'orchestrator.main' 2>/dev/null || true
sleep 1

if [[ "${USE_VLM}" -eq 1 ]]; then
  svc_start r1-vlm-daemon.service
  echo "[install] waiting for P5b vlm socket (up to 8 min)..."
  bash "${AGENT_ROOT}/scripts/wait_vlm_sock.sh" /tmp/r1-vlm.sock 240 || true
  SOCK="/tmp/r1-vlm.sock"
else
  svc_start r1-llm-daemon.service
  echo "[install] waiting for llm socket (up to 90s)..."
  for _ in $(seq 1 90); do
    [[ -S /tmp/r1-llm.sock ]] && break
    sleep 1
  done
  SOCK="/tmp/r1-llm.sock"
fi
if [[ -S "${SOCK}" ]]; then
  chmod 777 "${SOCK}" 2>/dev/null || true
  svc_start r1-orchestrator.service
  if systemctl list-unit-files r1-webui.service >/dev/null 2>&1; then
    svc_start r1-webui.service
  fi
else
  echo "[install] WARN: infer socket not ready — check vlm/llm daemon logs" >&2
fi

# Disable GNOME Chromium autostart (WebUI via systemd r1-webui; avoids sudo/display D-state)
if [[ -f "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop" ]]; then
  rm -f "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop"
  echo "[install] removed login autostart Chromium (use r1-webui + PC forward or open_agent_gui.sh)"
fi

# Desktop icon + app menu entry
install -d "${DESKTOP_DIR}" "${APPS_DIR}" "${AUTOSTART_DIR}"
install -m 644 "${AGENT_ROOT}/scripts/xiaolan-agent.desktop" "${APPS_DIR}/xiaolan-agent.desktop"
cp "${APPS_DIR}/xiaolan-agent.desktop" "${DESKTOP_DIR}/小揽语音助手.desktop"
cp "${APPS_DIR}/xiaolan-agent.desktop" "${DESKTOP_DIR}/xiaolan-agent.desktop"
chmod 755 "${DESKTOP_DIR}/xiaolan-agent.desktop" "${DESKTOP_DIR}/小揽语音助手.desktop" 2>/dev/null || true
chown -R "${USER_NAME}:${USER_NAME}" "${DESKTOP_DIR}" "${APPS_DIR}" "${AUTOSTART_DIR}" 2>/dev/null || true

# Trust desktop launcher (GNOME — required or double-click opens text editor)
chmod +x "${AGENT_ROOT}/scripts/trust_desktop_launcher.sh" 2>/dev/null || true
bash "${AGENT_ROOT}/scripts/trust_desktop_launcher.sh" "${USER_NAME}" || true

# Larger desktop icons + text (HDMI small screen)
chmod +x "${AGENT_ROOT}/scripts/scale_desktop_icons.sh" 2>/dev/null || true
bash "${AGENT_ROOT}/scripts/scale_desktop_icons.sh" "${USER_NAME}" 128 2.25 || true

# Tech-style wallpaper
bash "${AGENT_ROOT}/scripts/set_tech_wallpaper.sh" "${USER_NAME}" || true

# GUI autostart via systemd only (avoid duplicate GNOME + systemd Chromium launches).
if [[ -f "${AGENT_ROOT}/scripts/xiaolan-gui-autostart.desktop" ]]; then
  install -m 644 "${AGENT_ROOT}/scripts/xiaolan-gui-autostart.desktop" \
    "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop"
  sed -i 's/^Hidden=false/Hidden=true/; s/^X-GNOME-Autostart-enabled=true/X-GNOME-Autostart-enabled=false/' \
    "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop" 2>/dev/null || true
  chown "${USER_NAME}:${USER_NAME}" "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop" 2>/dev/null || true
fi

if [[ -f "${AGENT_ROOT}/systemd/r1-agent-gui.service" ]]; then
  install -m 644 "${AGENT_ROOT}/systemd/r1-agent-gui.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable r1-agent-gui.service
  systemctl restart r1-agent-gui.service || true
fi

systemctl --no-pager status r1-llm-daemon.service --lines=3 || true
systemctl --no-pager status r1-orchestrator.service --lines=3 || true
systemctl --no-pager status r1-webui.service --lines=3 2>/dev/null || true
systemctl --no-pager status r1-agent-gui.service --lines=3 2>/dev/null || true

if [[ -x "${AGENT_ROOT}/scripts/install_wifi_ap.sh" ]]; then
  bash "${AGENT_ROOT}/scripts/install_wifi_ap.sh" || echo "[install] WARN: WiFi AP setup failed (see logs/wifi_ap.log)" >&2
fi

echo ""
echo "[install] done"
echo "  开机栈: r1-mediamtx + r1-mediamtx-frame (缓存) + vlm/llm + orchestrator + webui (:8766) + r1-agent-gui"
echo "  PC 测试: adb forward tcp:8765 tcp:8765 && adb forward tcp:8766 tcp:8766"
echo "  浏览器: http://127.0.0.1:8766  (API/WS :8765)"
echo "  可选 HDMI 全屏: bash ${AGENT_ROOT}/scripts/open_agent_gui.sh"
echo "  壁纸: ${AGENT_ROOT}/ui/wallpaper.svg"
echo "  打开 GUI: 双击桌面「小揽语音助手」"
