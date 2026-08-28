# R1 Agent — 流式对话智能体（P5）

youyeetoo R1（RK3588S）+ RM1828（RK1828）端侧对话智能体。

**当前阶段：** Phase A–E ✅ · Phase F 流式 Paraformer ASR ✅ · Matcha TTS ✅ · HDMI 桌面 GUI ✅

## 桌面 GUI 与自启

| 项 | 路径 / 端口 |
|----|-------------|
| 控制面板 | `agent/ui/index.html` · HTTP **8766** · Chromium 全屏 |
| WebSocket 状态 | `ws://127.0.0.1:8765/ws` |
| 桌面图标 | `~/Desktop/小揽语音助手.desktop` |
| 登录自启 GUI | systemd `r1-agent-gui.service`（GNOME autostart 已禁用防双开） |
| 语音服务自启 | `r1-llm-daemon` + `r1-orchestrator`（systemd） |
| FY-SP701 + adb | [`docs/ADB_SP701_COEXIST.md`](docs/ADB_SP701_COEXIST.md) · `install_usb_adb_mic_boot.sh` |
| 科技风壁纸 | `/userdata/agent/ui/wallpaper.svg` |
| 一键安装 | `sudo bash /userdata/agent/scripts/install_autostart.sh` |
| 打开 GUI | 双击桌面图标 · 或 `bash /userdata/agent/scripts/open_agent_gui.sh` |

PC 推送：`powershell -File agent/scripts/push_agent.ps1`

## 与现有代码的关系

| 目录 | 角色 |
|------|------|
| `../voice/` | P3.5 板载 ES8388 · P3.6 FY-SP701 USB 模组（`fy_sp701_*.sh`） |
| `../p4/` | RTSP + VLM 看图原型 · `see()` 能力来源 |
| `agent/` | **P5 新架构**：常驻 daemon + 流式编排 |

板端部署目标路径：`/userdata/agent/`（与 `/userdata/voice/`、`/userdata/p4/` 并列）。

## 文档

- [`docs/TECH_PLAN.md`](docs/TECH_PLAN.md) — **v1.0 技术方案**（常驻模型四件套 · IPC · 阶段）
- [`docs/PHASE_3_6.md`](docs/PHASE_3_6.md) — **Phase 3.6** FY-SP701 V3 USB 阵列麦 + 功放验收
- [`docs/ADB_SP701_COEXIST.md`](docs/ADB_SP701_COEXIST.md) — FY-SP701 与 adb 调试口共存
- [`docs/ASR_STREAMING.md`](docs/ASR_STREAMING.md) — **Phase F** streaming Paraformer ASR
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 架构概览

**常驻模型：** InternVL3.5-4B **LLM-only**（`/userdata/models/InternVL3_5-4B/` llm 四件套 · ~236MB · 1828）

## 目录规划（定型后按 TECH_PLAN 填充）

```
agent/
├── daemon/          # 1828 LLM 常驻进程（C++ · RKNN3 Session）
├── orchestrator/    # 3588 对话编排（Python · 状态机）
├── asr/             # 流式 ASR / VAD 封装
├── tts/             # 分句 TTS / 播放队列
├── vision/          # see() · RTSP 最新帧 · VLM 调度
├── proto/           # IPC 消息定义（JSON Lines / Unix socket）
├── ui/              # HDMI 控制面板（Chromium 全屏 · WS 8765）
└── scripts/         # 部署 · systemd · 桌面自启 · 壁纸
```

## 快速链接

- 路线图 Canvas：`r1-vlm-agent-roadmap.canvas.tsx`
- Phase F Canvas：`asr-streaming-paraformer.canvas.tsx`
- 语音硬件冻结：`../voice/scripts/voice_hw_board.sh`
