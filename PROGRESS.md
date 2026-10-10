# youyeetoo R1 + RM1828 项目进展

> 最后更新：2026-08-28  
> 板端：R1 · Ubuntu 22.04 · kernel 5.10.110 **#12**  
> 加速卡：RK1828 · FW/API **1.0.5b10**

---

## 总览

| 阶段 | 状态 | 门禁 |
|------|------|------|
| P0 硬件通电 | ✅ 完成 | lspci 182a · adb 可连 |
| P1 软件栈 | ✅ 完成 | rknn-smi 36/5120MB · Qwen3-0.6B ~155 tok/s |
| P2 静态看图 | ✅ 完成 | InternVL3.5-4B 448² 端到端描述正确 |
| P3 纯文本对话 | ✅ 完成 | LLM-only · 不加载 vision · ~80 tok/s |
| P4 RTSP 1fps | ✅ 原型通过 | RTSP tcp 640×480 → 448² 短描述 |
| P5 智能体 | 🔵 进行中 | llm_daemon + orchestrator · 流式语音 · HDMI GUI |
| P6 产品化 | 🔵 部分 | systemd 自启 · 桌面 GUI · 壁纸 |

**产品目标模型：** InternVL3.5-4B（448² · W4A16 · thinking 关）

---

## P3 纯文本 LLM（2026-08-21 22:00 · 已通过）

### 路径说明

| 场景 | 工具 | 是否加载 vision |
|------|------|----------------|
| 纯文本聊天 | `rknn3_session_test`（仅 llm 四件套） | ❌ 不加载 |
| 看图描述 | `rknn_internvl3_demo`（六件套 + 图片） | ✅ 必跑 vision |

> `rknn_internvl3_demo` 在 init 时同时加载 vision + llm，并在 inference 前必跑 vision encoder。**纯聊天勿用此 demo。**

### 测试结果

**命令：**
```bash
cd /userdata/models/InternVL3_5-4B
rknn3_session_test \
  llm_InternVL3_5-4B.rknn \
  llm_InternVL3_5-4B.weight \
  InternVL3_5-4B.tokenizer.gguf \
  InternVL3_5-4B.embed.bin \
  1024 128 0xff
```

| 测试 | Prefill | Generate |
|------|---------|----------|
| 中文「相对论…」 | 134.6 ms · **148 tok/s** | 1582 ms · **80.3 tok/s** |
| 英文「relativity…」 | 119.5 ms · **176 tok/s** | 1587 ms · **80.0 tok/s** |

- 输出：完整中文/英文相对论解释（128 token 截断）
- 显存：**~236 MB**（LLM-only）vs VLM 端到端 **~3 GB+**
- thinking：session_test 无 thinking 路径

### P5 预留

交互式多轮 Agent（保留 context、用户输入循环）在 **P5** 实现；P3 仅验证 LLM 主干可独立于 vision 推理。

---

## P2 InternVL3.5-4B 端到端（2026-08-21 21:57 · 已通过）

| 指标 | 结果 |
|------|------|
| Vision | 448×448 · **191.33 ms** |
| Prefill | 488 ms / 305 tok ≈ **625 tok/s** |
| 输出 | ✅ 宇航员月球喝啤酒（与 demo.jpg 一致） |

**路径：** `/userdata/rknn_InternVLM_demo/` · `/userdata/models/InternVL3_5-4B/`

```bash
cd /userdata/rknn_InternVLM_demo
export LD_LIBRARY_PATH=./lib:/usr/lib
./rknn_internvl3_demo \
  /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.rknn \
  /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.weight \
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.rknn \
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.weight \
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.tokenizer.gguf \
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.embed.bin \
  0xff 0xff model/demo.jpg "Describe this image in one sentence."
```

---

## P2 Qwen3-VL-4B（2026-08-21 21:43 · 已通过）

- 修复：1.0.5b10 库 + 584 字节头重编 `rknn_qwen3_vl_demo`
- Vision **121.8 ms** · Prefill ~485 tok/s

---

## P1 已完成

- kernel #12 · EP inbound ATU · HugePage 160
- Qwen3-0.6B ~155 tok/s
- **禁止** 手动 `rknn3_startup restart`；用 adb reboot 冷启动

---

## 关键路径

| 资源 | 路径 |
|------|------|
| InternVL 模型 | `InternVL3_5-4B/` · `/userdata/models/InternVL3_5-4B/` |
| InternVL demo | `rknn_InternVLM_demo/` · `/userdata/rknn_InternVLM_demo/` |
| Canvas | `%USERPROFILE%\.cursor\projects\empty-window\canvases\r1-vlm-agent-roadmap.canvas.tsx` |

---

## P4 RTSP 1fps（2026-08-21 · 原型通过）

| 项 | 值 |
|----|-----|
| R1 静态 IP | 192.168.2.100/24 · gw 192.168.2.1 |
| RTSP | rtsp://192.168.2.169:554/stream_2 · TCP · h264 |
| 流分辨率 | 640×480 → 中心裁剪 448×448 |
| 脚本 | `/userdata/p4/scripts/` |

**冒烟结果（RTSP 实拍）：**
> 这是一张办公室的图片，显示了一张桌子和一扇玻璃门。

Vision ~190 ms · 整轮含模型加载 ~30 s（stock demo 每次 reload）。

```bash
bash /userdata/p4/scripts/net_static.sh
bash /userdata/p4/scripts/p4_test.sh
bash /userdata/p4/scripts/p4_loop.sh 3
```

**已知限制：** 勿与 `voice_chat` 同时占 1828；连续 VLM 需 cold reboot 或 P5 常驻进程。

---

## P5 智能体 + 桌面 GUI（2026-08-27 · 进行中）

| 项 | 状态 |
|----|------|
| `llm_daemon` + `r1-orchestrator` systemd | ✅ enable |
| 流式 VAD · Paraformer ASR · Matcha TTS | ✅ |
| persona 兜底 · pipelined TTS · barge-in | ✅ |
| HDMI 全屏 GUI（Chromium :8766 · WS :8765） | ✅ |
| 登录自启 GUI + 桌面图标 + 科技风壁纸 | ✅ |
| 大屏布局：标题「语音助手」· 紧凑状态栏 | ✅ |
| FY-SP701 USB 麦 + adb 调试口共存 | ✅ [`docs/ADB_SP701_COEXIST.md`](agent/docs/ADB_SP701_COEXIST.md) |

```bash
# PC 推送 + 安装
powershell -File agent/scripts/push_agent.ps1
adb shell sudo bash /userdata/agent/scripts/install_autostart.sh

# SP701 + adb 共存（板端）
sudo bash /userdata/agent/scripts/install_usb_adb_mic_boot.sh

# 手动打开 GUI
bash /userdata/agent/scripts/open_agent_gui.sh
```

---

## 待办

- [x] P4：GStreamer RTSP tcp · 640×480 · 448² 短描述
- [x] P5 基础：llm_daemon · orchestrator · 流式语音 · HDMI GUI
- [ ] P5b：VLM spike → 统一 vlm_daemon / see()
- [ ] P5：InternVL chat template · llm_daemon 重编
- [ ] DTS 持久化 `hugepages=160`
---

## 项目文档与网页整理（2026-10-09）

- 新增根目录 `README.md`：结构、架构、部署、资源边界与阶段进度。
- 新增 `docs/site/` 交互式项目介绍：架构节点、模块入口、阶段筛选与展开。
- GitHub Pages 工作流只发布 `docs/site/`，与板端 `agent/ui/` 实时控制面板独立。
- 整理当前工作区实现：音频 / 系统调试面板、录音回放与直通、WiFi AP 局域网访问。
- 本轮为源码与文档整理，不更新历史硬件验收日期或性能结果。
- 当前正常回答在完整生成与清洗后才进入 TTS；token 流式显示不代表全链路流式首响。
- `agent/vision/` 尚未实现；RTSP 原型的取帧目标 1fps 不代表 VLM 每秒输出一次描述。
