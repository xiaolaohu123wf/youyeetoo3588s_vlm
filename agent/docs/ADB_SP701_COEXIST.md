# FY-SP701 与 adb 共存

> **硬件**：adb 调试口（USB gadget）与 FY-SP701 Host USB **必须是两个口**。  
> **根因（2026-08-28）**：`/usr/bin/usbdevice` 启动时 `. /etc/profile`，其中 `alsactl restore -f /etc/asound.state` 在 SP701（`cafe:b20a`）插入后因新 USB 声卡不在 state 文件中而失败；脚本使用 `sh -e`，整进程退出 → adb gadget 挂掉。  
> 日志里的 `Found hardware: "USBcafe:b20a"` 来自 **alsactl**，不是无关提示。

## 症状

| 现象 | 说明 |
|------|------|
| 插 SP701 后 PC `adb devices` 为空 | `usbdevice.service` failed 或 `adbd` 不在 |
| 冷启动两根线都插着 adb 失败 | 开机时序：Host 枚举与 gadget 启动抢资源 |
| 等 30–60s 又恢复 | 延迟启动 / retry / guard 生效 |
| orchestrator 崩溃 `mic_arm.sh` exit 1 | 见下文 mic_arm 修复 |

## 一键安装（板端 root）

```bash
sudo bash /userdata/agent/scripts/install_usb_adb_mic_boot.sh
```

或串口无 adb 时：

```bash
sudo bash /userdata/agent/scripts/apply_adb_sp701_fix_now.sh
```

PC 有 adb 时：

```powershell
powershell -File agent\scripts\deploy_usb_adb_mic_fix.ps1
```

## 机制

| 组件 | 作用 |
|------|------|
| `patch_alsactl_profile.sh` | `/etc/profile` 中 `alsactl restore ... \|\| true` |
| `usbdevice.service.d/delay-for-host-usb.conf` | 首次启动延迟 20s |
| `r1-usbdevice-retry.service` | 开机后最多 5 次 retry |
| `99-r1-sp701-adb-recover.rules` | SP701 热插触发 recover |
| `recover_adb_after_sp701.sh` | 90s 开机保护 + UDC 复位 + 多次重试 |
| `r1-adb-guard.service` | SP701 在线时每 8s 检查并恢复 adb |

## 验收

```bash
# SP701 已插 Host 口、PC adb 线已接调试口
sudo bash /userdata/agent/scripts/test_sp701_adb.sh
adb devices
pgrep -a adbd
tail -5 /userdata/agent/logs/adb_guard.log
```

**预期**：`test_sp701_adb.sh` → `PASS`；插拔麦后 adb 可能闪断数秒，guard 自动拉回。

## 相关修复（同批部署）

- **`voice/scripts/mic_arm.sh`**：`ROUTE` 在 `set -u` 下未定义即退出（orchestrator 子进程无 env）→ 先 `source voice_env.sh` 再赋值。
- **`wait_fy_sp701.sh`** + `r1-orchestrator.service`：auto profile 等待 SP701 ALSA card（最多 45s）。
- **`open_agent_gui.sh`**：Chromium `flock` + 清除 `SingletonLock`；`install_autostart.sh` 禁用 GNOME 重复自启（仅 systemd 拉 GUI）。

## 故障排查

```bash
grep alsactl /etc/profile
systemctl status usbdevice r1-adb-guard r1-usbdevice-retry --no-pager
journalctl -u usbdevice -n 30 --no-pager
tail -30 /userdata/agent/logs/adb_sp701_recover.log
tail -10 /userdata/agent/logs/adb_guard.log
cat /tmp/usbdevice.log | tail -30
lsusb | grep -iE 'cafe|Timesintelli'
```

| 现象 | 处理 |
|------|------|
| 刚插麦 adb 断 | 等 30–60s 或 `apply_adb_sp701_fix_now.sh` |
| `failed to start rockchip: -19` | UDC 忙；recover 会复位，或冷启后等 boot grace |
| profile 未 patch | 重跑 `patch_alsactl_profile.sh` |
| orchestrator 仍用 board | `systemctl restart r1-orchestrator`，确认 SP701 在 `lsusb` |

## 文件清单

```
agent/scripts/patch_alsactl_profile.sh
agent/scripts/install_usb_adb_mic_boot.sh
agent/scripts/apply_adb_sp701_fix_now.sh
agent/scripts/recover_adb_after_sp701.sh
agent/scripts/adb_guard_loop.sh
agent/scripts/retry_usbdevice.sh
agent/scripts/test_sp701_adb.sh
agent/scripts/wait_fy_sp701.sh
agent/scripts/deploy_usb_adb_mic_fix.ps1
agent/systemd/r1-adb-guard.service
agent/systemd/r1-adb-sp701-recover.service
agent/systemd/r1-usbdevice-retry.service
agent/systemd/99-r1-sp701-adb-recover.rules
```
