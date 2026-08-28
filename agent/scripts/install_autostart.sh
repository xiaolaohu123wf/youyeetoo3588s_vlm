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
install -m 644 "${AGENT_ROOT}/systemd/r1-orchestrator.service" /etc/systemd/system/
systemctl daemon-reload

# Stop manual/orphan processes before enabling services
pkill -f "orchestrator.main" 2>/dev/null || true
pkill -f "/userdata/agent/bin/llm_daemon" 2>/dev/null || true
rm -f "${AGENT_ROOT}/run/orchestrator.pid" "${AGENT_ROOT}/run/llm_daemon.pid" /tmp/r1-llm.sock
sleep 1

systemctl enable r1-llm-daemon.service r1-orchestrator.service
systemctl restart r1-llm-daemon.service || true
echo "[install] waiting for llm socket (up to 120s)..."
for _ in $(seq 1 120); do
  [[ -S /tmp/r1-llm.sock ]] && break
  sleep 1
done
if [[ -S /tmp/r1-llm.sock ]]; then
  chmod 777 /tmp/r1-llm.sock 2>/dev/null || true
  systemctl restart r1-orchestrator.service || true
else
  echo "[install] WARN: llm socket not ready — journalctl -u r1-llm-daemon -n 30" >&2
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
install -m 644 "${AGENT_ROOT}/scripts/xiaolan-gui-autostart.desktop" \
  "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop"
sed -i 's/^Hidden=false/Hidden=true/; s/^X-GNOME-Autostart-enabled=true/X-GNOME-Autostart-enabled=false/' \
  "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop" 2>/dev/null || true
chown "${USER_NAME}:${USER_NAME}" "${AUTOSTART_DIR}/xiaolan-gui-autostart.desktop" 2>/dev/null || true

install -m 644 "${AGENT_ROOT}/systemd/r1-agent-gui.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable r1-agent-gui.service
systemctl restart r1-agent-gui.service || true

systemctl --no-pager status r1-llm-daemon.service --lines=3 || true
systemctl --no-pager status r1-orchestrator.service --lines=3 || true
systemctl --no-pager status r1-agent-gui.service --lines=3 || true

echo ""
echo "[install] done"
echo "  后台服务: systemctl status r1-llm-daemon r1-orchestrator"
echo "  桌面图标: ${DESKTOP_DIR}/xiaolan-agent.desktop"
echo "  开机自启: systemd 语音服务 + r1-agent-gui + GNOME autostart"
echo "  壁纸: ${AGENT_ROOT}/ui/wallpaper.svg"
echo "  打开 GUI: 双击桌面「小揽语音助手」"
