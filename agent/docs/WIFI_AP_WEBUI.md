# WiFi AP + PC WebUI

板载 WiFi（`wlP4p65s0`）开热点，电脑连上后浏览器打开控制面板（与 HDMI 同源 `agent/ui`）。

## 默认参数

| 项 | 值 |
|----|-----|
| SSID | `YouYeetoo-R1` |
| 密码 | `youyeetoo1` |
| WebUI | `http://10.42.0.1:8766/`（NM 热点常见网关） |
| WebSocket | `ws://10.42.0.1:8765/ws` |

修改 SSID/密码：复制 `config/wifi_ap.env.example` → `/userdata/agent/config/wifi_ap.env` 后 `sudo systemctl restart r1-wifi-ap`.

## 安装（板端）

```bash
sudo bash /userdata/agent/scripts/install_wifi_ap.sh
bash /userdata/agent/scripts/wifi_ap_status.sh
```

PC 完整部署后 `install_autostart.sh` 会自动尝试安装 AP 服务。

## PC 部署

```powershell
powershell -File agent/scripts/push_local_deploy.ps1
```

本地仓库已包含 [Wangpengyu01/youyeetoo3588s_vlm](https://github.com/Wangpengyu01/youyeetoo3588s_vlm) 主线之上的 FY-SP701 / GUI / 调试面板等更新。

## 注意

- HDMI  kiosk 仍用 `127.0.0.1`；PC 通过 AP IP 访问时 UI 自动连对应主机 WebSocket。
- adb USB 调试与 WiFi AP 互不冲突。
