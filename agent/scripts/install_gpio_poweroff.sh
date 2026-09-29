#!/usr/bin/env bash
# ==============================================================================
# R1 / RK3588 GPIO 安全关机服务 一键安装与管理脚本
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="r1-gpio-poweroff.service"
SERVICE_SRC="${AGENT_ROOT}/systemd/${SERVICE_NAME}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

COLOR_GREEN="\033[32m"
COLOR_YELLOW="\033[33m"
COLOR_RED="\033[31m"
COLOR_CYAN="\033[36m"
COLOR_RESET="\033[0m"

if [[ $EUID -ne 0 ]]; then
   echo -e "${COLOR_RED}错误: 请使用 root 权限执行此脚本 (sudo bash $0)${COLOR_RESET}" 
   exit 1
fi

do_install() {
  echo -e "${COLOR_CYAN}============================================================${COLOR_RESET}"
  echo -e "${COLOR_CYAN}    正在安装 R1 GPIO 硬件安全关机服务 (${SERVICE_NAME})    ${COLOR_RESET}"
  echo -e "${COLOR_CYAN}============================================================${COLOR_RESET}"

  chmod +x "${SCRIPT_DIR}/gpio_poweroff_monitor.py"

  if [[ ! -f "${SERVICE_SRC}" ]]; then
    echo -e "${COLOR_RED}找不到服务文件: ${SERVICE_SRC}${COLOR_RESET}"
    exit 1
  fi

  echo -e "• 安装服务单元到 ${SERVICE_DST}..."
  cp -f "${SERVICE_SRC}" "${SERVICE_DST}"
  chmod 644 "${SERVICE_DST}"

  echo -e "• 重载 systemd 守护进程..."
  systemctl daemon-reload

  echo -e "• 启用并启动服务..."
  systemctl enable "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"

  sleep 1
  echo ""
  echo -e "${COLOR_GREEN}✓ 安装成功！当前服务运行状态:${COLOR_RESET}"
  systemctl status "${SERVICE_NAME}" --no-pager || true
  echo ""
  echo -e "${COLOR_YELLOW}提示: 物理接线为方案一: GPIO 39 (GPIO1_A7) 与 GND 之间接轻触开关。${COLOR_RESET}"
  echo -e "${COLOR_YELLOW}持续长按 1.5 秒即自动触发小揽安全停机并关机。${COLOR_RESET}"
}

do_status() {
  systemctl status "${SERVICE_NAME}" --no-pager
}

do_stop() {
  echo -e "${COLOR_YELLOW}正在停止并禁用 GPIO 关机服务...${COLOR_RESET}"
  systemctl stop "${SERVICE_NAME}" || true
  systemctl disable "${SERVICE_NAME}" || true
  echo -e "${COLOR_GREEN}已停止。${COLOR_RESET}"
}

do_test() {
  echo -e "${COLOR_CYAN}正在暂停后台服务进行前台交互测试...${COLOR_RESET}"
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  echo -e "${COLOR_CYAN}启动 GPIO 仿真测试模式 (长按 1.5s 不会真关机，仅在屏幕打印触发日志，Ctrl+C 退出)...${COLOR_RESET}"
  python3 "${SCRIPT_DIR}/gpio_poweroff_monitor.py" --test --pin 39 --hold-time 1.5 || true
  echo -e "${COLOR_YELLOW}正在恢复后台守护服务...${COLOR_RESET}"
  systemctl start "${SERVICE_NAME}" 2>/dev/null || true
  echo -e "${COLOR_GREEN}后台服务已恢复运行。${COLOR_RESET}"
}

do_scan() {
  echo -e "${COLOR_CYAN}正在暂停后台服务进行引脚扫描...${COLOR_RESET}"
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  echo -e "${COLOR_CYAN}启动 GPIO 引脚实时扫描器 (测试短接任意引脚与 GND，Ctrl+C 退出)...${COLOR_RESET}"
  python3 "${SCRIPT_DIR}/gpio_poweroff_monitor.py" --scan || true
  echo -e "${COLOR_YELLOW}正在恢复后台守护服务...${COLOR_RESET}"
  systemctl start "${SERVICE_NAME}" 2>/dev/null || true
  echo -e "${COLOR_GREEN}后台服务已恢复运行。${COLOR_RESET}"
}

ACTION="${1:-install}"
case "${ACTION}" in
  install)
    do_install
    ;;
  status)
    do_status
    ;;
  stop)
    do_stop
    ;;
  test)
    do_test
    ;;
  scan)
    do_scan
    ;;
  *)
    echo "用法: sudo $0 {install|status|stop|test|scan}"
    exit 1
    ;;
esac
