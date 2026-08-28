import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Code,
  CollapsibleSection,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  TodoList,
  UsageBar,
  computeDAGLayout,
  useCanvasState,
  useHostTheme,
  useMemo,
} from "cursor/canvas";

const CANVAS_PATH =
  "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\canvases\\r1-vlm-agent-roadmap.canvas.tsx";

const PHASES = [
  {
    id: "p0",
    name: "P0 硬件通电",
    days: "完成",
    gate: "lspci 见 182a · Ubuntu 22.04",
    work: "刷官方镜像、12V、M.2、PCIe 枚举",
  },
  {
    id: "p1",
    name: "P1 软件栈",
    days: "完成",
    gate: "Qwen3-0.6B 推理 ~155 tok/s",
    work: "pcie-rkep 内核 + BAR2/HugePage + RKNN3 冒烟",
  },
  {
    id: "p2",
    name: "P2 静态看图",
    days: "完成",
    gate: "InternVL3.5-4B 448² 端到端通过",
    work: "Qwen3 + InternVLM rknn demo 验收",
  },
  {
    id: "p3",
    name: "P3 纯文本对话",
    days: "完成",
    gate: "无图 LLM 推理 · 不加载 vision",
    work: "rknn3_session_test 仅 llm 四件套",
  },
  {
    id: "p3v",
    name: "P3.5 语音 I/O",
    days: "验收冻结",
    gate: "voice_hw_board v2 · asr_tts 验收通过",
    work: "板载麦 + J368 stereo · 换麦/降噪留 P5+",
  },
  {
    id: "p36",
    name: "P3.6 FY-SP701",
    days: "验收通过",
    gate: "phase_3_6 --live · 11 PASS · Agent 集成待做",
    work: "USB 阵列麦+功放 · plughw:1,0 · 与 P3.5 独立",
  },
  {
    id: "p4",
    name: "P4 RTSP 看图",
    days: "原型通过",
    gate: "p4_test · VLM+TTS · p4_check_1828",
    work: "RTSP 取帧 · InternVL 短描述 · J368 TTS 播报",
  },
  {
    id: "p5",
    name: "P5 智能体",
    days: "进行中",
    gate: "llm_daemon 常驻 · 流式 chat 2–4s 首响",
    work: "Ollama 式 LLM-only · VAD/ASR/TTS · agent/ 代码库",
  },
  {
    id: "p6",
    name: "P6 产品化",
    days: "按需",
    gate: "开机自启、看门狗、日志指标",
    work: "systemd / OTA · llm_chat 替代 patch",
  },
] as const;

const TODOS: Record<
  string,
  { id: string; content: string; status: "pending" | "in_progress" | "completed" }[]
> = {
  p0: [
    { id: "p0-1", content: "确认 R1（RK3588S）· V2/V3 M.2 规格", status: "completed" },
    { id: "p0-2", content: "RM1828 插背面 M.2 M-Key + 独立 12V", status: "completed" },
    { id: "p0-3", content: "官方 Ubuntu 22.04 烧 eMMC（kernel 5.10.110）", status: "completed" },
    { id: "p0-4", content: "lspci 见 Device 182a · adb shell 可连板端", status: "completed" },
  ],
  p1: [
    { id: "p1-1", content: "userspace rknpu_rk182x_m2_v1.0.5b10 + rknn3.service", status: "completed" },
    { id: "p1-2", content: "内核集成 pcie-rkep.c · CONFIG_PCIE_FUNC_RKEP=y", status: "completed" },
    { id: "p1-3", content: "CONFIG_HUGETLBFS=y + bootargs hugepages=160（32M）", status: "completed" },
    { id: "p1-4", content: "刷 zboot.img · /dev/pcie-rkep-0003:31:00.0 存在", status: "completed" },
    { id: "p1-5", content: "rknn-smi -v：Driver 3.3.1 · FW 1.0.5b10 · API 1.0.5b10", status: "completed" },
    { id: "p1-6", content: "HugePages 160×32MB + hugetlbfs /dev/hugepages 已挂载", status: "completed" },
    { id: "p1-7", content: "lspci BAR2 = 0x9c0000000（64M）— 硬件分配正常", status: "completed" },
    { id: "p1-8", content: "根因：obj_info ep_bar2_phy_addr 未写入 → userspace 读 bar2=0", status: "completed" },
    { id: "p1-9", content: "pcie-rkep probe + SYNC 补丁 · zboot.img 已产出（待刷 boot）", status: "completed" },
    { id: "p1-10", content: "kernel #11 EP inbound ATU bar2+0x2000 → rknn-smi 32/5120MB", status: "completed" },
    { id: "p1-10b", content: "kernel #12 ATU 读回误判修复 · 冷启动 32/5120MB 稳定", status: "completed" },
    { id: "p1-10c", content: "Qwen3-0.6B v1.0.4 rknn3_session_test · ~155 tok/s", status: "completed" },
  ],
  dev: [
    { id: "dev-1", content: "编译 VM gp@192.168.100.196 · Docker R1 SDK", status: "completed" },
    { id: "dev-2", content: "RK182X SDK pcie-rkep 源合并进 R1 kernel 5.10", status: "completed" },
    { id: "dev-3", content: "DTS rk3588s-yyt.dts bootargs hugepages=160 持久化", status: "pending" },
    { id: "dev-4", content: "adb shell 板端测试脚本（延时 startup / 固件 MD5）", status: "completed" },
    { id: "dev-5", content: "板端诊断：fan_ctrl GPIO 占风扇 · pwm6 disabled · pwm-fan 未绑定", status: "completed" },
    { id: "dev-6", content: "DTS：fan_ctrl disabled · pwm-fan 绑定 febd0020.pwm · hwmon0", status: "completed" },
    { id: "dev-7", content: "kernel CONFIG_PWM_FAN=y · 编 rk3588s-yyt.img → 只烧 zboot.img", status: "completed" },
    { id: "dev-8", content: "刷机验收：hwmon0/pwm1 手动 200/64 回读 OK · 自动温控待观察", status: "completed" },
  ],
  p2: [
    { id: "p2-0", content: "Qwen3-VL-4B v1.0.4 下载到 PC（~3.3GB）", status: "completed" },
    { id: "p2-1", content: "adb push → /userdata/models/Qwen3-VL-4B/（6 文件）", status: "completed" },
    { id: "p2-2", content: "Vision 编码器 rknn3_model_test 384² 通过", status: "completed" },
    { id: "p2-3", content: "LLM 纯文本 rknn3_session_test ~80 tok/s 通过", status: "completed" },
    { id: "p2-4", content: "rknn3_vlm_demo embed 失败（错误工具，已弃用）", status: "completed" },
    { id: "p2-5", content: "rknn_qwen3_vl_demo 1.0.5b10 重编 + 端到端通过", status: "completed" },
    { id: "p2-6", content: "下载 InternVL3_5-4B 六件套 → PC + 板端", status: "completed" },
    { id: "p2-7", content: "编译 rknn_internvl3_demo（1.0.5b10 库+584 头）", status: "completed" },
    { id: "p2-8", content: "InternVL 448² 板端端到端测试 · Vision 191ms", status: "completed" },
  ],
  p3: [
    { id: "p3-1", content: "纯文本路径：rknn3_session_test 仅 llm 四件套（不加载 vision）", status: "completed" },
    { id: "p3-2", content: "1024 ctx · 中英文双 prompt · Generate ~80 tok/s", status: "completed" },
    { id: "p3-3", content: "显存对比：LLM-only ~236MB vs VLM ~3GB+", status: "completed" },
    { id: "p3-5", content: "2026-08-22 板端复验：stock /usr/bin + llm_ask · 无需 VM 编译", status: "completed" },
    { id: "p3-4", content: "交互式多轮 Agent（P5 实现，非本关）", status: "pending" },
  ],
  p3v: [
    { id: "p3v-1", content: "离线部署 sherpa-onnx + SenseVoice + VITS → /userdata/voice/", status: "completed" },
    { id: "p3v-2", content: "mic_probe 确认 MIC_ROUTE=main_board（headset 全静音）", status: "completed" },
    { id: "p3v-3", content: "SH1.25 J368 GND+L+R stereo · PLAYBACK_CHANNELS=2", status: "completed" },
    { id: "p3v-3b", content: "voice_hw_board.sh 冻结录音/播放参数（2026-08-22）", status: "completed" },
    { id: "p3v-3c", content: "mic_arm：播放后关 Headset Mic · 板载麦可录", status: "completed" },
    { id: "p3v-3d", content: "v2 电平优化验收：peak~697 · ASR+TTS 全通（2026-08-22 15:00 冻结）", status: "completed" },
    { id: "p3v-4", content: "asr.sh 对齐 mic_diag（mono · prep boost · 无 ITN）", status: "completed" },
    { id: "p3v-5", content: "voice_chat 端到端：ASR→LLM→TTS 跑通", status: "completed" },
    { id: "p3v-6", content: "llm_ask.py 动态 prompt（session_test patch 临时）", status: "completed" },
    { id: "p3v-7", content: "TTS 归一化 peak 26k · 截断 120 字 · LLM max_new=64", status: "completed" },
    { id: "p3v-8", content: "延迟优化：VAD/流式 ASR · 常驻进程 · 跳过 debug 回放", status: "pending" },
    { id: "p3v-9", content: "SDK 编译正式 llm_chat（替代 binary patch）", status: "pending" },
    { id: "p3v-10", content: "换麦 → FY-SP701 V3 已到 · P3.6 独立验收（板载仍冻结）", status: "completed" },
    { id: "p3v-11", content: "play_wav route guard：PulseAudio 播中关 Headphone Switch 修复", status: "completed" },
  ],
  p36: [
    { id: "p36-1", content: "USB 枚举：cafe:b20a Timesintelli · ALSA card1 plughw:1,0", status: "completed" },
    { id: "p36-2", content: "fy_sp701_*.sh + analyze_stereo_wav.py + phase_3_6_test.sh", status: "completed" },
    { id: "p36-3", content: "双麦立体声 STEREO_OK · peak~21k · SenseVoice「你好」", status: "completed" },
    { id: "p36-4", content: "16 kHz · 模块功放播放 · TTS 经 USB 喇叭", status: "completed" },
    { id: "p36-5", content: "AEC 粗测：播放 tone 时 peak 未异常飙升", status: "completed" },
    { id: "p36-6", content: "--live 验收 11 PASS · fy_sp701_asr_tts 闭环", status: "completed" },
    { id: "p36-7", content: "docs/PHASE_3_6.md · git e55bcb2", status: "completed" },
    { id: "p36-8", content: "Agent vad.alsa_device → plughw:1,0 · VAD 热切换", status: "pending" },
    { id: "p36-9", content: "TtsEngine 播放路由 fy_sp701_play.sh（或 ALSA_DEVICE env）", status: "pending" },
    { id: "p36-10", content: "Streaming Paraformer 实时全双工实机（FY-SP701 I/O）", status: "pending" },
    { id: "p36-11", content: "GUI 设置 Modal：输入/输出设备 · 音色 · 语速", status: "pending" },
    { id: "p36-12", content: "WS settings_get/set + user_settings.json 持久化", status: "pending" },
    { id: "p36-13", content: "ANC 专项噪声对比（P3.6b 可选）", status: "pending" },
    { id: "p36-14", content: "修复 wav_to_16k_mono append_fade_out tuple bug", status: "pending" },
  ],
  p4: [
    { id: "p4-1", content: "静态 IP 192.168.2.100 + ping 192.168.2.169", status: "completed" },
    { id: "p4-2", content: "GStreamer rtspsrc tcp + mppvideodec 640×480 取帧", status: "completed" },
    { id: "p4-3", content: "frame_prepare 448² + rknn_internvl3_demo 短描述", status: "completed" },
    { id: "p4-4", content: "p4_test / p4_loop / push_p4.ps1 · /userdata/p4/", status: "completed" },
    { id: "p4-5", content: "wait_rknn pipefail 修复 · p4_check_1828 显存预检", status: "completed" },
    { id: "p4-6", content: "vlm_see + p4_tts：看图描述 J368 喇叭播报（P4_TTS=1）", status: "completed" },
  ],
  p5: [
    { id: "p5-a1", content: "llm_daemon：InternVL3.5-4B LLM-only 四件套 ~236MB 1828 常驻", status: "completed" },
    { id: "p5-a2", content: "orchestrator：asyncio · VAD 始终监听 · streaming Paraformer ASR", status: "completed" },
    { id: "p5-a3", content: "Matcha TTS 流水线播放 + barge-in · E2E 首响 <4s", status: "completed" },
    { id: "p5-a4", content: "agent.yaml persona 兜底 · agent_api WS · HDMI GUI", status: "completed" },
    { id: "p5-s1", content: "并行 spike：VLM 六件套 text-only 可跳过 vision？", status: "pending" },
    { id: "p5-b1", content: "P5b see()：spike 过→统一 vlm_daemon；不过→按需 VLM", status: "pending" },
    { id: "p5-c1", content: "HDMI 全屏 GUI + 登录自启 + 壁纸 + 桌面图标", status: "completed" },
    { id: "p5-c2", content: "GUI 设置按钮：输入/输出设备 · 音色 · 语速（与退出并排）", status: "pending" },
    { id: "p5-c3", content: "AudioProfileManager：board vs fy_sp701 · IDLE 时热切换", status: "pending" },
  ],
  p6: [
    { id: "p6-1", content: "rknn3.service ExecStartPre=sleep 5（proxy 时序）", status: "pending" },
    { id: "p6-2", content: "r1-llm-daemon + r1-orchestrator systemd · GUI 登录自启", status: "completed" },
  ],
};

const PROGRESS_LOG = [
  { date: "2026-08-21 11:25", item: "立项", detail: "端侧对话智能体 + RM1828；初误写 YY3588，后更正为 R1" },
  { date: "2026-08-21 11:32", item: "方案", detail: "锁定 InternVL3.5-4B：纯对话 + RTSP 1fps 短看图" },
  { date: "2026-08-21 11:52", item: "系统", detail: "拒绝 R1 Dcompile/Debian 重编；锁定官方 Ubuntu 22.04 img" },
  { date: "2026-08-21 12:09", item: "P0", detail: "Recovery/Boot/OTG 烧录排障；V3 拨码 DEVICE + USB-A" },
  { date: "2026-08-21 14:12", item: "P0", detail: "Ubuntu 烧录成功；adb shell；lspci 见 182a" },
  { date: "2026-08-21 14:15", item: "P1", detail: "选 rknpu_rk182x_m2_v1.0.5b10_installer_arm64.tgz 安装" },
  { date: "2026-08-21 14:20", item: "P1", detail: "rknn-smi Failed to initialize；journal：failed to get pcie-rkep.ko" },
  { date: "2026-08-21 14:23", item: "诊断", detail: "安装包无 .ko；/lib/modules 不存在；CONFIG_PCIE_FUNC_RKEP 未开" },
  { date: "2026-08-21 14:31", item: "内核", detail: "确认需 Ucompile 编 pcie-rkep；用户有 3588buildsdk VM" },
  { date: "2026-08-21 15:42", item: "编译环境", detail: "R1 SDK SCP 到 VM；Docker Ubuntu 20.04 编内核" },
  { date: "2026-08-21 15:50", item: "编译环境", detail: "Cursor Remote-SSH 代理修复（176:7890；删 apt 99proxy 旧 7899）" },
  { date: "2026-08-21 16:00+", item: "内核", detail: "RK182X SDK V1.0.5B10 pcie-rkep 合并；禁 PCIEASPM_EXT" },
  { date: "2026-08-21 17:00+", item: "内核", detail: "开 HUGETLB；DTS bootargs hugepages；产出 zboot.img 刷 boot" },
  { date: "2026-08-21 18:20", item: "P1", detail: "pcie-rkep 通；HugePage 160 页；仍 bar2_phy=0 · Re-Init 失败" },
  { date: "2026-08-21 18:48", item: "adb 测试", detail: "延时 startup/固件 MD5/console 全测；排除固件/时序问题" },
  { date: "2026-08-21 18:52", item: "根因", detail: "lspci BAR2=9c0000000 但 obj_info 未同步；probe 补丁编译中" },
  { date: "2026-08-21 18:54", item: "Canvas", detail: "完整历史写入 Canvas 可折叠区；说明永久保存方式" },
  { date: "2026-08-21 19:10", item: "内核", detail: "SYNC 补丁 zboot.img 产出（15MB）；曾尝试烧录后疑似不开机" },
  { date: "2026-08-21 19:30", item: "恢复", detail: "重刷官方 Ubuntu · UART 1500000 · 系统正常进桌面" },
  { date: "2026-08-21 21:00", item: "adb 复测", detail: "官方 kernel #4 · 无 pcie-rkep · 无 HUGETLBFS · RKNN3 重装" },
  { date: "2026-08-21 21:02", item: "阻塞", detail: "rknn-smi Failed · No pcie-rkep devices · 须单刷 zboot.img" },
  { date: "2026-08-21 21:00", item: "zboot 验收", detail: "kernel #7 · pcie-rkep · HugePage 160 · ep_bar2=9c0000000 SYNC OK" },
  { date: "2026-08-21 21:00", item: "仍阻塞", detail: "userspace bar2_phy=0 · ddr load addr failed · Chip Count 0 · Memory NA" },
  { date: "2026-08-21 21:05", item: "kernel #11", detail: "EP inbound ATU bar2+0x2000 idx=3 cpu=0x4fa000000 · rknn-smi 32/5120MB" },
  { date: "2026-08-21 21:16", item: "模型更正", detail: "正确路径=EP inbound ATU（非 RC inbound）；bar4 -110 属预期" },
  { date: "2026-08-21 21:16", item: "收尾", detail: "ATU 读回 0xffffffff 误判 → 需 kernel #12 停无意义重试" },
  { date: "2026-08-21 21:20", item: "kernel #12", detail: "adb 冷启动验收：32/5120MB · Chip Count 1 · ATU 无重试" },
  { date: "2026-08-21 21:27", item: "P1 完成", detail: "Qwen3-0.6B v1.0.4 推理 OK · Prefill ~500 TPS · Generate ~155 TPS" },
  { date: "2026-08-21 20:47", item: "P2 模型", detail: "Qwen3-VL-4B 6 文件 adb push → /userdata/models/Qwen3-VL-4B/" },
  { date: "2026-08-21 20:52", item: "P2 Vision", detail: "rknn3_model_test vision 384² 通过 · 4 路 FP16 输出正常" },
  { date: "2026-08-21 20:55", item: "P2 LLM", detail: "rknn3_session_test llm 部分 ~80 tok/s · 中英文 OK" },
  { date: "2026-08-21 20:58", item: "P2 阻塞", detail: "rknn3_vlm_demo → text_with_chat_template_token_id failed" },
  { date: "2026-08-21 21:30", item: "P2 根因", detail: "API 1.0.4 vs 1.0.5b10 · rknn3_tensor_attr 512 vs 584" },
  { date: "2026-08-21 21:42", item: "P2 修复", detail: "pkgroot 1.0.5b10 库 + 584 头重编 rknn_qwen3_vl_demo" },
  { date: "2026-08-21 21:43", item: "P2 Qwen3 ✅", detail: "Vision 121.8ms · Prefill 485tok/s · 宇航员描述正确" },
  { date: "2026-08-21 21:44", item: "P2 切换", detail: "Qwen3 验收完成 · 开始 InternVL3.5-4B 448²" },
  { date: "2026-08-21 21:57", item: "P2 InternVL ✅", detail: "rknn_internvl3_demo · Vision 191ms · 宇航员描述正确" },
  { date: "2026-08-21 22:00", item: "P3 完成", detail: "session_test 仅 llm · 中英文 · ~80 tok/s · 236MB 无 vision" },
  { date: "2026-08-21 22:10", item: "P3.5 语音", detail: "架构锁定：3588 CPU ASR/TTS · 1828 仅 LLM" },
  { date: "2026-08-21 22:15", item: "P3.5 部署", detail: "sherpa SenseVoice + VITS + espeak → /userdata/voice/" },
  { date: "2026-08-21 22:20", item: "P3.5 咪头", detail: "板载麦 Line1→MicL 路由修复；ALC NG 关 mute ADC" },
  { date: "2026-08-21 22:30", item: "P3.5 喇叭", detail: "左声道 Mono(Left) · play_wav · PLAYBACK_GAIN 2.5" },
  { date: "2026-08-21 22:35", item: "P3.5 LLM+TTS", detail: "test_llm_tts 通过 · InternVL 纯文本 ~80 tok/s" },
  { date: "2026-08-21 22:45", item: "P3.5 外接咪", detail: "默认 headset_miclr · 立体声录 · 录完回放再 ASR" },
  { date: "2026-08-21 22:50", item: "P3.5 阻塞", detail: "外接咪头路由待 mic_probe 确认 · 削波/静音导致 ASR 空" },
  { date: "2026-08-21 22:55", item: "P3.5 路由", detail: "mic_probe ×2：headset 全 peak=1 · main_board peak 1805–4818" },
  { date: "2026-08-21 22:58", item: "P3.5 ASR", detail: "mic_diag OK：「hello hello 可以听得见吗」· peak 18238" },
  { date: "2026-08-21 23:00", item: "P3.5 修复", detail: "asr.sh 对齐 mic_diag · mono · 去掉 use-itn · 2>&1" },
  { date: "2026-08-21 23:02", item: "P3.5 E2E ✅", detail: "voice_chat：ASR→Intern-S1 LLM→TTS 合成成功 · TTS 播放勿 Ctrl+C" },
  { date: "2026-08-21 23:10", item: "P4 网络", detail: "NM 静态 192.168.2.100/24 · ping 192.168.2.169 OK" },
  { date: "2026-08-21 23:12", item: "P4 RTSP", detail: "h264 tcp 640×480 取帧 ~2.5s · mppvideodec" },
  { date: "2026-08-21 23:03", item: "P3.5 延迟", detail: "ASR/TTS/VLM reload 统一优化留 P5 · 流式+常驻" },
  { date: "2026-08-21 23:15", item: "P4 VLM ✅", detail: "办公室+桌子+玻璃门 · Vision 190ms · 脚本 /userdata/p4/" },
  { date: "2026-08-21 23:16", item: "P4 脚本", detail: "net_static · rtsp_grab · vlm_see · p4_test · push_p4.ps1" },
  { date: "2026-08-22 14:52", item: "P3.5 硬件冻结", detail: "SH1.25 GND+L/R stereo · main_board · voice_hw_board.sh" },
  { date: "2026-08-22 14:55", item: "P3.5 电平优化", detail: "mic gain 8 · prep boost · TTS normalize peak 26k" },
  { date: "2026-08-22 15:00", item: "P3.5 验收冻结", detail: "asr_tts 识别相对论 · TTS peak=26000 · 换麦暂缓" },
  { date: "2026-08-22 15:12", item: "P4 TTS", detail: "vlm_see → p4_tts · J368 播报看图描述 · P4_TTS=1" },
  { date: "2026-08-22 15:12", item: "P4 1828", detail: "wait_rknn pipefail 修复 · p4_check_1828 · MODEL_SETUP 预检" },
  { date: "2026-08-22 15:25", item: "P3 Session", detail: "确认无需改源码/VM 编译 · 板端 /usr/bin/rknn3_session_test 直接测" },
  { date: "2026-08-22 15:28", item: "P3 复验 ✅", detail: "adb push llm_ask · stock Prefill 162tok/s Generate 74tok/s · llm_ask 动态 prompt OK" },
  { date: "2026-08-22 15:32", item: "Canvas ⑱", detail: "ASR·TTS·看图说话 三大验收命令专节 · Windows adb 一键" },
  { date: "2026-08-26 11:53", item: "PWM6 风扇", detail: "板端：fan_ctrl GPIO state=1 满速 · pwm6 disabled · pwm-fan 未绑定" },
  { date: "2026-08-26 11:56", item: "Canvas ⑲", detail: "PWM6 风扇 DTS 改造规格 · VM 编 boot 验收清单" },
  { date: "2026-08-26 12:07", item: "PWM6 ✅", detail: "hwmon0/pwmfan · pwm-fan 已绑定 · fan_ctrl 移除 · echo 200/64 手动调速 OK" },
  { date: "2026-08-26 12:09", item: "喇叭无声", detail: "PulseAudio 播中关 Headphone Switch · aplay 成功 peak~26k 但 J368 无声" },
  { date: "2026-08-26 12:22", item: "喇叭 ✅", detail: "play_wav spk_route_guard · Headphone=on · speaker_test 用户确认可听" },
  { date: "2026-08-26 12:22", item: "Canvas ⑳", detail: "J368 喇叭 PulseAudio/ES8388 路由冲突 · 根因与验收" },
  { date: "2026-08-26 13:35", item: "P5 TECH v1", detail: "TECH_PLAN v1.0 锁定 · InternVL3.5-4B LLM-only llm_daemon · spike→P5b" },
  { date: "2026-08-26 13:35", item: "Canvas ㉑", detail: "P5 常驻模型规格 · 阶段 A–E · VLM spike · agent/ 代码库" },
  { date: "2026-08-26 18:00", item: "P5 Agent", detail: "llm_daemon · orchestrator Phase E · Matcha TTS · Paraformer ASR" },
  { date: "2026-08-26 20:00", item: "P5 修复", detail: "persona 兜底 · pipelined TTS · LLM socket 权限 · barge-in" },
  { date: "2026-08-27 11:30", item: "HDMI GUI", detail: "Chromium 全屏 · WS 控制面板 · 桌面图标 · 退出按钮" },
  { date: "2026-08-27 11:45", item: "桌面产品化", detail: "科技风 wallpaper.svg · systemd 自启 · 登录自动开 GUI · 2.25× 缩放" },
  { date: "2026-08-28 17:22", item: "P3.6 硬件", detail: "FY-SP701 V3 USB · cafe:b20a · card1 plughw:1,0 · 2MIC+5W功放" },
  { date: "2026-08-28 17:30", item: "P3.6 脚本", detail: "fy_sp701_*.sh · phase_3_6_test.sh · PHASE_3_6.md · commit e55bcb2" },
  { date: "2026-08-28 17:37", item: "P3.6 --live ✅", detail: "11 PASS · 双麦 peak~21k · ASR「你好」· asr_tts 闭环 · AEC 粗测 OK" },
  { date: "2026-08-28 17:40", item: "P3.6→P5", detail: "Agent FY-SP701 集成 + GUI 设置 Modal 待办写入 Canvas" },
  { date: "2026-08-21 23:16", item: "里程碑", detail: "P0–P4 原型全通 · P5 流式语音+GUI 进行中" },
] as const;

const STATUS_LAYERS = [
  ["硬件 / PCIe 枚举", "✅", "lspci 182a · BAR2 9c0000000"],
  ["pcie-rkep + HugePage + 固件", "✅", "160×32MB · FW 1.0.5b10"],
  ["EP inbound ATU bar2 → hugepage", "✅", "bar2+0x2000 idx=3 cpu=0x4fa000000"],
  ["rknn-smi Memory 5120MB", "✅", "36 / 5120 · Chip 0 Online · 41°C"],
  ["Qwen3-0.6B LLM 冒烟", "✅", "v1.0.4 · Generate ~155 tok/s"],
  ["Qwen3-VL-4B Vision", "✅", "384² · rknn3_model_test 通过"],
  ["Qwen3-VL-4B LLM 文本", "✅", "rknn3_session_test ~80 tok/s"],
  ["Qwen3-VL-4B 端到端 VLM", "✅", "rknn_qwen3_vl_demo · Vision 122ms · 1.0.5b10"],
  ["InternVL3.5-4B 端到端 VLM", "✅", "rknn_internvl3_demo · Vision 191ms · 448²"],
  ["InternVL3.5-4B LLM 纯文本", "✅", "session_test · ~80 tok/s · 236MB 无 vision"],
  ["3588 语音 ASR", "✅ 冻结", "main_board · prep boost · peak~697 可识别"],
  ["3588 语音 TTS", "✅ 冻结", "normalize peak 26k · stereo · route guard"],
  ["语音对话闭环", "✅ 冻结", "asr_tts / voice_chat · voice_hw_board v2"],
  ["FY-SP701 USB I/O", "✅ P3.6", "plughw:1,0 · 双麦 · 模块功放 · --live 11 PASS"],
  ["FY-SP701 → Agent", "⏳ 集成中", "vad+TTS 路由 · Streaming Paraformer · GUI 设置"],
  ["P4 RTSP 取流", "✅", "192.168.2.169 tcp h264 · 640×480 · ~2.5s"],
  ["P4 RTSP 短描述", "✅", "InternVL · Vision 190ms · p4_test"],
  ["P4 TTS 播报", "✅", "p4_tts · voice_hw v2 · 描述朗读"],
  ["1828 预检", "✅", "p4_check_1828 · >80MB 拒绝 VLM"],
  ["P5 llm_daemon 常驻", "✅", "systemd · /tmp/r1-llm.sock · ~236MB"],
  ["P5 orchestrator 流式", "✅", "VAD · Paraformer · Matcha TTS · barge-in"],
  ["P5 HDMI GUI", "✅", "Chromium 全屏 :8766 · WS :8765 · 登录自启"],
  ["桌面壁纸/图标", "✅", "wallpaper.svg · ding 128px · trusted launcher"],
] as const;

const P4_E2E_RESULTS = [
  ["静态 IP", "192.168.2.100/24", "NM 持久 · reboot 后仍在", "✅"],
  ["ping 摄像机", "192.168.2.169", "1.0–1.8 ms", "✅"],
  ["RTSP 取帧", "stream_2 · h264 tcp", "640×480 · ~2.5s · mppvideodec", "✅"],
  ["VLM 输出", "用一句话描述当前画面", "椅子+网状结构等", "✅"],
  ["TTS 播报", "p4_tts · P4_TTS=1", "J368 stereo · peak 26000", "✅ 2026-08-22"],
  ["整轮耗时", "stock demo 冷加载", "Vision ~190ms · 整轮 ~30s", "⚠️ P5 热待机"],
  ["1828 冲突", "voice_chat 后跑 VLM", "MODEL_SETUP fail · 300MB", "⚠️ p4_check/reboot"],
] as const;

const P4_CONFIG = [
  ["R1 IP", "192.168.2.100/24", "gw 192.168.2.1"],
  ["RTSP", "rtsp://192.168.2.169:554/stream_2", "protocols=tcp"],
  ["解码", "GStreamer + mppvideodec", "RK3588S 硬解"],
  ["VLM 输入", "640×480 → 448² 中心裁剪", "frame_prepare.py"],
  ["TTS", "P4_TTS=1 · p4_tts.sh", "自动 source voice_hw_board v2"],
  ["1828 预检", "p4_check_1828.sh", "显存 >80MB → 提示 reboot"],
  ["板端路径", "/userdata/p4/scripts/", "PC: youyeetoo3588s/p4/"],
] as const;

const P5_1828_SCHEDULER = [
  ["v1 常驻", "llm_daemon · LLM-only", "InternVL3.5-4B 四件套 ~236MB · Ollama 式"],
  ["v1 不做", "see() / 统一 VLM", "P5b · 并行 spike 后定案"],
  ["3588 语音", "VAD + sherpa ASR/TTS", "CPU · 不用 3588 NPU"],
  ["编排", "Python asyncio + socket", "agent/orchestrator/"],
  ["触屏", "HDMI GUI · WS :8765", "Chromium 全屏 :8766 · 登录自启 ✅"],
  ["spike S1", "text-only 跳过 vision?", "Prefill 与 LLM-only 差 <200ms"],
  ["spike S2", "同 Session 图文交替", "无 Aborted · 上下文连贯"],
  ["P5b 候选", "统一 vlm_daemon ~3GB", "spike 全过则替换 llm_daemon"],
] as const;

/** llm_daemon 常驻模型（TECH_PLAN v1.0 §1） */
const P5_LLM_DAEMON_MODEL = [
  ["模型", "InternVL3.5-4B", "Intern-S1 对话 · RKNN3 W4A16"],
  ["形态", "LLM-only", "不加载 vision_*.rknn/weight"],
  ["Runtime", "RKNN3 1.0.5b10", "RM1828 EP · 非 Ollama/GGUF"],
  ["目录", "/userdata/models/InternVL3_5-4B/", "板端已 push"],
  ["llm.rknn", "llm_InternVL3_5-4B.rknn", "结构"],
  ["llm.weight", "llm_InternVL3_5-4B.weight", "权重"],
  ["tokenizer", "InternVL3_5-4B.tokenizer.gguf", "chat template"],
  ["embed", "InternVL3_5-4B.embed.bin", "词嵌入"],
  ["ctx / new", "1024 / 64", "keep_history=1 · 8–10 轮"],
  ["显存", "~236 MB", "vs VLM 六件套 ~3GB+"],
  ["性能", "Prefill ~120ms · ~80 tok/s", "P3 实测基准"],
  ["源码", "voice/src/rknn3_session_test.cpp", "fork → llm_daemon"],
  ["Socket", "/tmp/r1-llm.sock", "JSON Lines 流式 token"],
] as const;

const P5_IMPL_PHASES = [
  ["A", "llm_daemon + llm_client", "10 轮 · TTFT <500ms", "✅"],
  ["B", "VAD 始终监听 + orchestrator", "Silero VAD · 端点检测", "✅"],
  ["C", "streaming Paraformer ASR", "partial/final · bilingual", "✅"],
  ["D", "Matcha TTS 流水线", "E2E 首响 <4s · barge-in", "✅"],
  ["E", "agent.yaml + agent_api WS + HDMI GUI", "全屏 Chromium · 自启", "✅"],
  ["P5c", "GUI 设置 + 音频 Profile 切换", "输入/输出 · 音色 · 语速", "pending"],
  ["S", "VLM spike S1–S3", "与 A 并行", "pending"],
  ["P5b", "see() 或 vlm_daemon", "spike 定案", "deferred"],
] as const;

const P5_DESKTOP_GUI = [
  ["控制面板", "agent/ui/index.html", "标题「语音助手」· 三对话框 · 退出"],
  ["设置（待）", "与退出并排 · Modal", "输入/输出设备 · 音色 · 语速 · P5c"],
  ["HTTP", "127.0.0.1:8766", "python3 http.server · open_agent_gui.sh"],
  ["WebSocket", "127.0.0.1:8765/ws", "state · asr · llm_token · tts_sentence"],
  ["浏览器", "/usr/bin/chromium", "--start-fullscreen · 勿用 firefox snap"],
  ["登录自启", "xiaolan-gui-autostart.desktop", "autostart_agent_gui.sh"],
  ["桌面图标", "小揽语音助手.desktop", "trust_desktop_launcher.sh"],
  ["壁纸", "ui/wallpaper.svg", "set_tech_wallpaper.sh · 科技风"],
  ["缩放", "scale_desktop_icons.sh", "icon 128px · text 2.25×"],
  ["安装", "install_autostart.sh", "systemd + GUI + 壁纸一键"],
] as const;

const P5_DECISIONS_LOCKED = [
  ["D1", "v1 chat only · see P5b", "✅ 2026-08-26"],
  ["D2", "始终监听 + VAD", "✅"],
  ["D3", "ASR 3588 CPU sherpa", "✅"],
  ["D4", "Python asyncio + C++ daemon", "✅"],
  ["D5", "InternVL3.5-4B LLM-only 四件套", "✅"],
  ["D6", "v1 LLM → spike → 统一 vlm", "✅"],
  ["D7", "HDMI GUI + 登录自启 + 壁纸", "✅ 2026-08-27"],
] as const;

const NEXT_MILESTONES = [
  ["P3.6 集成", "FY-SP701 → Agent 全链路", "vad+TTS · Streaming Paraformer 实机"],
  ["P5c 设置", "GUI Modal + WS settings API", "board / fy_sp701 Profile 切换"],
  ["Spike S", "VLM 统一常驻可行性", "并行 · 不过则 P5b 按需 VLM"],
  ["P5b", "see() 或 vlm_daemon", "spike 全过则替换 llm_daemon"],
  ["P5 G-b", "InternVL chat template", "llm_daemon 重编 · 提示词服从"],
  ["P6", "看门狗 · OTA · 指标", "rknn3 时序 · 日志"],
] as const;

const VOICE_HW_FROZEN = [
  ["状态", "✅ 2026-08-22 15:00 冻结", "换麦 / 降噪暂缓至后续"],
  ["录音", "MIC_ROUTE=main_board", "gain=8 · mono · MIC_GAIN_LOCK=1"],
  ["ASR 增益", "prep_asr_wav.py", "peak<8000 → 目标 16000（max 25x）"],
  ["播放", "SH1.25 GND+L+R", "PLAYBACK_ROUTE=headphone · normalize→26000 · ch=2"],
  ["播放守护", "play_wav.sh spk_route_guard", "PulseAudio 播中保持 Headphone Switch=on"],
  ["禁止", "3.5mm TRS 插入", "录音时勿插；J368 并联喇叭即可"],
  ["入口", "voice_hw_board.sh v2", "asr_tts.sh · voice_chat.sh 自动 source"],
] as const;

/** FY-SP701 V3 USB 阵列麦 + 功放（P3.6 · 与 P3.5 独立） */
const P36_HW = [
  ["USB ID", "cafe:b20a Timesintelli", "Bus 001 Device 003"],
  ["ALSA", "card 1 · plughw:1,0", "采集+播放同卡 · 16 kHz"],
  ["双麦", "2MIC 线性 · stereo", "L/R peak 一致 · analyze_stereo_wav.py"],
  ["功放", "8Ω 5W · 模块喇叭", "fy_sp701_play.sh · 勿叠加大增益"],
  ["固件算法", "AEC/ANC/AGC/DNN", "黑盒 · USB 仅出 PCM · 无 ASR 文本 API"],
  ["R1 ASR", "Streaming Paraformer", "模组修音 + R1 流式识别 · 非模组 ASR"],
  ["脚本", "fy_sp701_hw.sh", "独立于 voice_hw_board.sh"],
  ["验收", "phase_3_6_test.sh --live", "2026-08-28 · 11 PASS · 0 FAIL"],
] as const;

const P36_E2E_RESULTS = [
  ["USB 枚举", "lsusb + aplay/arecord -l", "card1 可见", "✅"],
  ["功放播放", "880/660 Hz tone", "模块喇叭可听", "✅"],
  ["双麦采集", "3s stereo", "peak~21368 · STEREO_OK", "✅"],
  ["16 kHz", "mono 分析", "48000 samples @16k", "✅"],
  ["AEC 粗测", "安静 vs 播 tone", "18951→19985 未飙升", "✅ 粗测"],
  ["ASR smoke", "SenseVoice offline", "「你好」", "✅"],
  ["TTS 播放", "模块功放", "华芸模组播放测试…", "✅"],
  ["asr_tts 闭环", "fy_sp701_asr_tts.sh", "识别+复读完成", "✅ --live"],
  ["Agent 集成", "vad+TTS 路由", "仍 plughw:0,0", "⏳ 下一步"],
  ["GUI 设置", "设备/音色/语速", "Modal 未实现", "⏳ P5c"],
] as const;

const P36_ALGO_AUDIT = [
  ["AEC 回声抑制", "模组 DSP", "粗测 peak 比通过", "⚠️ 非全双工对话"],
  ["ANC 噪声抑制", "模组 DSP", "无粉噪对比实验", "❌ 未验收"],
  ["AGC 自动增益", "模组 DSP", "peak~21k 间接迹象", "⚠️ 未隔离"],
  ["DNN", "模组 DSP", "无独立探针", "— 黑盒"],
  ["AES", "模组 DSP", "未单独测", "❌ 未验收"],
  ["ASR（模组）", "模组固件", "无 USB 文本输出", "N/A"],
  ["ASR（R1）", "Paraformer 流式", "P3.6 离线 OK · 实时待集成", "⏳"],
] as const;

const VOICE_E2E_RESULTS = [
  ["mic_probe", "headset/TRS 无麦", "四路 peak=1 · main_board 最佳", "✅ 锁定 main_board"],
  ["mic_diag", "板载麦 + 滴声", "peak 246–18238 · ASR OK", "✅"],
  ["asr_tts v2", "2026-08-22 15:00 冻结", "peak=697 · prep 12x · ASR 相对论", "✅ 验收"],
  ["TTS v2", "同轮 asr_tts", "normalize gain~5 · peak=26000 stereo", "✅ 验收"],
  ["喇叭路由", "2026-08-26 route guard", "Headphone Switch 播中 off → guard 修复", "✅ 用户确认"],
  ["voice_chat LLM", "Intern-S1", "LLM ~80 tok/s", "✅"],
  ["后续", "FY-SP701 V3", "P3.6 --live 11 PASS · Agent/GUI 集成中", "✅ 模组 / ⏳ 集成"],
] as const;

const VOICE_ACCEPTANCE = [
  ["硬件", "J368 GND+L+R · 勿插 3.5mm TRS", "—"],
  ["命令", "bash /userdata/voice/scripts/asr_tts.sh", "标准入口"],
  ["预期 HW", "[HW] 冻结配置 v2 · gain=8 · normalize→26000", "首行"],
  ["预期 MIC", "Headset=off · peak 500–3000", "SOFT_OK 可接受"],
  ["预期 ASR", "[ASR] 中文短句 · 非空", "勿 Ctrl+C 合成/播放"],
  ["预期 TTS", "peak=26000 · ch=2 · 播放完成", "音量已归一化"],
] as const;

const VOICE_LATENCY = [
  ["固定录音", "RECORD_SEC=5", "~5000 ms", "即使用户 2s 说完也等满 5s", "VAD 端点检测 · 改 3s"],
  ["离线 ASR", "sherpa-offline 整段", "~1–3 s", "每次冷启动加载模型", "流式 ASR 常驻进程"],
  ["LLM 1828", "llm_ask patch + session", "首轮 ~60 s · 后续 ~1–2 s", "每轮 patch 二进制", "SDK llm_chat 常驻 Session"],
  ["离线 TTS", "VITS 整句合成", "~2–5 s", "合成完才播放", "流式 TTS · 短句 ≤120 字"],
  ["Debug 回放", "monitor replay", "~5 s", "asr.sh 默认开启", "生产模式 VOICE_DEBUG=0 跳过"],
] as const;

const INFERENCE_RESULTS = [
  ["Qwen3-0.6B 中文", "请解释一下相对论的基本概念。", "39.6 ms", "505 tok/s", "1647 ms", "155 tok/s"],
  ["Qwen3-0.6B 英文", "Please explain the basic concept of relativity.", "31.6 ms", "664 tok/s", "1694 ms", "150 tok/s"],
] as const;

const P3_INFERENCE_RESULTS = [
  ["中文", "请解释一下相对论的基本概念。", "134.6 ms", "148 tok/s", "1582 ms", "80.3 tok/s"],
  ["英文", "Please explain the basic concept of relativity.", "119.5 ms", "176 tok/s", "1587 ms", "80.0 tok/s"],
] as const;

const P3_SESSION_REVERIFY = [
  ["stock session_test", "内置 prompt · max_new=64", "Prefill 123ms · 162 tok/s", "Generate 855ms · 74 tok/s", "✅ 2026-08-22"],
  ["llm_ask.py", "你好，请用一句话介绍你自己", "Intern-S1 自我介绍", "~28s（含模型加载）", "✅ 2026-08-22"],
  ["VM 交叉编译", "—", "本关不需要", "改 C++ / P5 llm_chat 时才需", "⏸ 待 P5"],
  ["push 范围", "llm_ask.py · test_llm_tts.sh", "未 push 二进制", "/usr/bin 已有官方版", "✅"],
] as const;

/** 三大用户验收链路：ASR · TTS · 看图说话（板端 adb shell） */
const E2E_THREE_FLOWS = [
  ["① ASR 识别", "mic_diag → asr 单测", "bash …/mic_diag.sh 5", "peak 500–3000 · [ASR] 中文非空", "J368 喇叭 · 勿插 3.5mm"],
  ["② TTS 播报", "喇叭 + 合成", "bash …/speaker_test.sh", "滴声 + TTS · Headphone=on", "play_wav route guard"],
  ["③ ASR→TTS", "听写复读（无 LLM）", "bash …/asr_tts.sh", "说中文 → 同句朗读", "⭐ P3.5 标准验收"],
  ["③b FY-SP701", "USB 阵列麦闭环", "bash …/phase_3_6_test.sh --live", "11 PASS · asr_tts 闭环", "⭐ P3.6 · plughw:1,0"],
  ["④ 说话对话", "ASR→LLM→TTS", "bash …/voice_chat.sh", "问句 → Intern-S1 答 → 朗读", "1828 LLM-only ~300MB"],
  ["⑤ 看图说话", "RTSP→VLM→TTS", "bash …/p4_test.sh", "画面描述 → J368 播报", "1828 VLM ~3GB · 摄像机在线"],
  ["1828 互斥", "voice_chat ↔ p4_test", "adb reboot && sleep 45", "p4_check_1828 通过后再跑 P4", "同 boot 不可混跑"],
] as const;

/** 板端实测（2026-08-26 · 风扇接 R1 PWM6 座） */
const FAN_DTS_AUDIT = [
  ["fan_ctrl (GPIO)", "lylx,xgpio · status=okay", "state=1 · 仅 0/1", "占控制权 · 导致常转"],
  ["pwm-fan", "DTS 有 cooling-levels/temp-trips", "驱动未绑定", "pwm6 未 enable"],
  ["pwm@febf0010 等", "设备树 status", "disabled", "PWM6 控制器关闭"],
  ["soc-thermal", "cooling-maps map0–3", "仅 cpufreq/devfreq", "未挂 pwm-fan"],
  ["CPU 温度 idle", "thermal_zone0", "~29°C", "非高温拉满"],
  ["临时关扇", "fan_ctrl/state", "echo 0 有效", "改 DTS 前权宜之计"],
] as const;

const FAN_DTS_CHECKLIST = [
  ["1 定位", "grep fan_ctrl pwm-fan pwm6 *yyt*.dts*", "arch/arm64/boot/dts/rockchip/"],
  ["2 禁用 GPIO", "fan_ctrl status = disabled", "释放风扇控制权"],
  ["3 开 PWM6", "&pwm6 okay + pwm6m0_pins", "Wiki 官方 PWM6 座"],
  ["4 pwm-fan", "pwms=&pwm6 · status=okay · temp-trips", "6 档 0–255"],
  ["5 soc-thermal", "map_fan0/1 → &fan", "推荐 · 与 Wiki 一致"],
  ["6 内核 config", "CONFIG_PWM_FAN=y 等", "rk3588_linux.config"],
  ["7 编译", "make rk3588s-yyt.img → zboot.img", "勿整包 3GB"],
  ["8 烧录", "RKDevTool 只勾 boot", "保留 rootfs/RKNN3"],
  ["9 验收", "cooling_device pwm-fan · idle cur_state≤1", "见 ⑲b"],
] as const;

/** 板端实测（2026-08-26 · J368 喇叭 PulseAudio 路由冲突修复） */
const SPK_ROUTE_VERIFY = [
  ["根因", "PulseAudio 15.99 + pasuspender + plughw aplay", "播中 Headphone Switch=off", "✅ 已定位"],
  ["表现", "aplay 成功 · peak~26000", "J368 无声 · 日志仍 [play] 完成", "静默失败"],
  ["为何曾正常", "v2 冻结走 headphone 路径", "桌面 PA 占卡后更易触发", "板载 Speaker 路径不受影响"],
  ["修复", "play_wav.sh spk_route_guard", "播中 30ms 轮询 + 播后 speaker_setup", "✅"],
  ["Headphone Switch", "amixer numid=28", "播后 values=on", "✅ adb"],
  ["Speaker Switch", "amixer numid=29", "values=off（headphone 路由）", "✅"],
  ["Mono Mux", "amixer numid=35", "stereo=0", "✅"],
  ["用户确认", "speaker_test.sh", "滴声 + TTS 可听", "✅ 2026-08-26"],
] as const;

const FAN_DTS_KERNEL_CONFIG = [
  ["CONFIG_PWM", "y", "PWM 子系统"],
  ["CONFIG_PWM_ROCKCHIP", "y", "Rockchip PWM 驱动"],
  ["CONFIG_PWM_FAN", "y", "pwm-fan 驱动"],
  ["CONFIG_SENSORS_PWM_FAN", "y", "hwmon pwm1"],
  ["CONFIG_THERMAL", "y", "温控框架"],
  ["CONFIG_THERMAL_OF", "y", "设备树 thermal"],
  ["CONFIG_ROCKCHIP_THERMAL", "y", "RK3588S 温度"],
] as const;

/** 刷机后板端实测（2026-08-26 · PWM DTS 已生效） */
const FAN_PWM_VERIFY = [
  ["pwm-fan 驱动", "platform/pwm-fan/driver", "pwm-fan 已绑定", "✅"],
  ["PWM 供应", "supplier febd0020.pwm", "对应 DTS &pwm6", "✅"],
  ["hwmon", "/sys/class/hwmon/hwmon0/name", "pwmfan", "✅"],
  ["fan_ctrl GPIO", "/sys/.../fan_ctrl/state", "节点已消失", "✅"],
  ["手动调速", "echo 200 > hwmon0/pwm1", "回读 200", "✅ adb 复验"],
  ["低档测试", "echo 64 > hwmon0/pwm1", "回读 64", "✅ adb 复验"],
  ["pwm1_enable", "—", "本板无此文件", "直接写 pwm1"],
  ["thermal map", "cooling_device type", "仍仅 cpufreq/devfreq", "⏸ 可选补 soc-thermal"],
] as const;

const VLM_INFERENCE_RESULTS = [
  ["Qwen3 Vision", "rknn3_model_test", "384×384 NHWC", "—", "4 路 FP16", "✅"],
  ["Qwen3 LLM 文本", "rknn3_session_test", "1024 ctx", "~124 tok/s", "~80 tok/s", "✅"],
  ["Qwen3 端到端", "rknn_qwen3_vl_demo", "demo.jpg 384²", "398ms/193tok", "Vision 122ms", "✅"],
  ["InternVL 端到端", "rknn_internvl3_demo", "demo.jpg 448²", "488ms/305tok", "Vision 191ms", "✅"],
  ["InternVL LLM 纯文本", "rknn3_session_test", "1024 ctx 无 vision", "~150 tok/s", "~80 tok/s", "✅"],
  ["InternVL RTSP 实拍", "rknn_internvl3_demo", "640→448² RTSP", "Prefill 520ms", "Vision 190ms", "✅"],
] as const;

const TEST_COMMANDS = {
  adb: [
    { label: "确认 adb 连接", cmd: "adb devices -l" },
    { label: "进入板端 shell", cmd: "adb shell" },
    { label: "重启板子（冷启动验收）", cmd: "adb reboot" },
    { label: "等待设备上线", cmd: "adb wait-for-device" },
  ],
  env: [
    { label: "内核版本 / 编译号", cmd: "uname -r && cat /proc/version | head -1" },
    { label: "内核配置（RKEP + HugePage）", cmd: "zcat /proc/config.gz | grep -E 'PCIE_FUNC_RKEP|HUGETLBFS'" },
    { label: "HugePage 状态", cmd: "grep -iE 'Huge|Hugetlb' /proc/meminfo" },
    { label: "PCIe 设备枚举", cmd: "lspci | grep -i 182" },
    { label: "BAR2 地址", cmd: "lspci -vv -s 0003:31:00.0 | grep -iE 'Region 2|LnkSta'" },
    { label: "pcie-rkep 设备节点", cmd: "ls -l /dev/pcie-rkep-*" },
    { label: "userdata 剩余空间", cmd: "df -h /userdata" },
  ],
  atu: [
    { label: "ATU 成功日志（应仅 1 条）", cmd: "dmesg | grep -i 'BAR2 inbound'" },
    { label: "ATU 误报重试计数（应为 0）", cmd: "dmesg | grep -ci 'all paths failed'; dmesg | grep -ci 'gave up'" },
    { label: "ep_bar2 + SYNC", cmd: "dmesg | grep -iE 'ep_bar2|update magic'" },
    { label: "bootargs HugePage", cmd: "cat /proc/cmdline | tr ' ' '\\n' | grep huge" },
  ],
  rknn: [
    { label: "⚠️ 冷启动验收（推荐，勿手动 restart）", cmd: "adb reboot && adb wait-for-device && sleep 45 && adb shell rknn-smi info" },
    { label: "版本信息", cmd: "rknn-smi -v" },
    { label: "设备 / 显存 / 温度", cmd: "rknn-smi info" },
    { label: "Chip 详情", cmd: "rknn-smi info -l" },
    { label: "rknn3 服务状态", cmd: "systemctl is-active rknn3.service rknn-mdns.service" },
    { label: "transfer_proxy 进程", cmd: "ps aux | grep transfer_proxy | grep -v grep" },
    { label: "❌ 避免：手动 restart 会 Re-Init 失败", cmd: "# rknn3_startup restart  → bar2_phy=0 · Memory NA" },
  ],
  modelWin: [
    { label: "Qwen3-0.6B 本地路径", cmd: "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\Qwen3-0.6B\\" },
    { label: "Qwen3-VL-4B 本地路径", cmd: "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\Qwen3-VL-4B\\" },
    { label: "推送 Qwen3-VL-4B", cmd: 'adb push "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\Qwen3-VL-4B" /userdata/models/' },
    { label: "模型下载（联想网盘）", cmd: "https://console.box.lenovo.com/l/H1fig1  提取码: rknn" },
    { label: "网盘 LLM 路径", cmd: "RKNN3_SDK/rknn3_models/v1.0.4/llm/Qwen3-0.6B/" },
    { label: "网盘 VLM 路径", cmd: "RKNN3_SDK/rknn3_models/v1.0.4/vlm/ → Qwen3-VL-4B · InternVL3.5-4B" },
  ],
  vlm: [
    { label: "Qwen3 Vision 单项", cmd: "cd /userdata/models/Qwen3-VL-4B && rknn3_model_test vision_Qwen3-VL-4B.rknn vision_Qwen3-VL-4B.weight 0xff" },
    { label: "Qwen3 端到端（✅ 已验证）", cmd: "cd /userdata/rknn_Qwen3_VL_demo && LD_LIBRARY_PATH=./lib:/usr/lib ./rknn_qwen3_vl_demo /userdata/models/Qwen3-VL-4B/vision_Qwen3-VL-4B.rknn /userdata/models/Qwen3-VL-4B/vision_Qwen3-VL-4B.weight /userdata/models/Qwen3-VL-4B/llm_Qwen3-VL-4B.rknn /userdata/models/Qwen3-VL-4B/llm_Qwen3-VL-4B.weight /userdata/models/Qwen3-VL-4B/Qwen3-VL-4B.tokenizer.gguf /userdata/models/Qwen3-VL-4B/Qwen3-VL-4B.embed.bin 0xff 0xff model/demo.jpg \"Describe this image in one sentence.\" 384 384 0.0" },
    { label: "InternVL 模型 PC 路径", cmd: "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\InternVL3.5-4B\\" },
    { label: "推送 InternVL 模型", cmd: 'adb push "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\InternVL3.5-4B" /userdata/models/' },
    { label: "InternVL 端到端（✅ 已验证）", cmd: "cd /userdata/rknn_InternVLM_demo && LD_LIBRARY_PATH=./lib:/usr/lib ./rknn_internvl3_demo /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.rknn /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.weight /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.rknn /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.weight /userdata/models/InternVL3_5-4B/InternVL3_5-4B.tokenizer.gguf /userdata/models/InternVL3_5-4B/InternVL3_5-4B.embed.bin 0xff 0xff model/demo.jpg \"Describe this image in one sentence.\"" },
  ],
  p3: [
    { label: "⭐【复验】stock session_test（无需编译）", cmd: "cd /userdata/models/InternVL3_5-4B && /usr/bin/rknn3_session_test llm_InternVL3_5-4B.rknn llm_InternVL3_5-4B.weight InternVL3_5-4B.tokenizer.gguf InternVL3_5-4B.embed.bin 1024 64 0xff" },
    { label: "⭐【复验】llm_ask 动态 prompt", cmd: "python3 /userdata/voice/scripts/llm_ask.py '你好，请用一句话介绍你自己'" },
    { label: "InternVL LLM 纯文本（P3 门禁 · 128 tok）", cmd: "cd /userdata/models/InternVL3_5-4B && rknn3_session_test llm_InternVL3_5-4B.rknn llm_InternVL3_5-4B.weight InternVL3_5-4B.tokenizer.gguf InternVL3_5-4B.embed.bin 1024 128 0xff" },
    { label: "验收显存（应 ~200–300MB，非 3GB+）", cmd: "rknn-smi info" },
    { label: "⚠️ internvl3_demo 必跑 vision，纯聊天勿用", cmd: "# 纯文本用 session_test；看图才用 rknn_internvl3_demo" },
  ],
  infer: [
    { label: "确认四文件齐全", cmd: "ls -lh /userdata/models/Qwen3-0.6B/" },
    { label: "LLM 推理冒烟", cmd: "cd /userdata/models/Qwen3-0.6B && rknn3_session_test Qwen3-0.6B.rknn Qwen3-0.6B.weight Qwen3-0.6B.tokenizer.gguf Qwen3-0.6B.embed.bin 1024 256 0xff" },
    { label: "rknn-console 列设备", cmd: "rknn-console rk1820 -l" },
  ],
  flash: [
    { label: "只烧 boot（保留 rootfs）", cmd: "RKDevTool → 勾选 boot → zboot.img（~15MB，非 boot.img）" },
    { label: "zboot 本地路径", cmd: "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\zboot.img" },
    { label: "Recovery 进 Loader", cmd: "V3: USB-A + 按 Recovery 上电 2–3s 松开" },
  ],
  voice: [
    { label: "⭐【验收】ASR→TTS 一键", cmd: "bash /userdata/voice/scripts/asr_tts.sh" },
    { label: "完整语音对话 ASR→LLM→TTS", cmd: "bash /userdata/voice/scripts/voice_chat.sh" },
    { label: "查看冻结参数", cmd: "source /userdata/voice/scripts/voice_hw_board.sh" },
    { label: "咪头+滴声+回放+ASR 诊断", cmd: "bash /userdata/voice/scripts/mic_diag.sh 5" },
    { label: "四路咪头路由探测", cmd: "python3 /userdata/voice/scripts/mic_probe.py" },
    { label: "立体声滴声+TTS 喇叭测试", cmd: "bash /userdata/voice/scripts/speaker_test.sh" },
    { label: "重听上次 ASR 录音", cmd: "bash /userdata/voice/scripts/replay_last.sh" },
    { label: "分析上次录音电平", cmd: "python3 /userdata/voice/scripts/analyze_wav.py /tmp/last_asr.wav" },
    { label: "仅 LLM+TTS（跳过录音）", cmd: "bash /userdata/voice/scripts/test_llm_tts.sh \"你好\"" },
    { label: "ES8388 咪头 mixer 状态", cmd: "bash /userdata/voice/scripts/mic_setup.sh" },
  ],
  p36: [
    { label: "⭐【P3.6 验收】--live 全项", cmd: "bash /userdata/agent/scripts/phase_3_6_test.sh --live" },
    { label: "USB 阵列麦 ASR→TTS 闭环", cmd: "bash /userdata/voice/scripts/fy_sp701_asr_tts.sh" },
    { label: "FY-SP701 诊断", cmd: "bash /userdata/voice/scripts/fy_sp701_mic_diag.sh 5" },
    { label: "检测 USB 声卡", cmd: "source /userdata/voice/scripts/fy_sp701_detect.sh" },
    { label: "USB 设备枚举", cmd: "lsusb | grep -iE 'cafe|Timesintelli|Audio'; aplay -l; arecord -l" },
    { label: "双麦立体声分析", cmd: "python3 /userdata/voice/scripts/analyze_stereo_wav.py /tmp/fy_sp701_mic_diag.wav" },
  ],
  p36Win: [
    { label: "推送 agent P3.6", cmd: "powershell -File C:\\Users\\wwff\\Documents\\youyeetoo3588s\\agent\\scripts\\push_agent.ps1" },
    { label: "推送 fy_sp701 脚本", cmd: "bash C:/Users/wwff/Documents/youyeetoo3588s/voice/scripts/push_voice.sh" },
  ],
  voiceWin: [
    { label: "PC 脚本目录", cmd: "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\" },
    { label: "推送 voice_hw_board.sh", cmd: 'adb push "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\voice_hw_board.sh" /userdata/voice/scripts/' },
    { label: "推送 asr_tts + asr + tts 链", cmd: 'adb push "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\asr_tts.sh" "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\asr.sh" "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\tts.sh" /userdata/voice/scripts/' },
    { label: "推送电平优化脚本", cmd: 'adb push "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\prep_asr_wav.py" "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\wav_to_16k_mono.py" "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\mic_arm.sh" /userdata/voice/scripts/' },
    { label: "推送 llm_ask + test_llm_tts", cmd: 'adb push "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\llm_ask.py" "C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\test_llm_tts.sh" /userdata/voice/scripts/' },
    { label: "去 CRLF + 可执行", cmd: 'adb shell "sed -i \'s/\\r$//\' /userdata/voice/scripts/*.sh; chmod +x /userdata/voice/scripts/*.sh"' },
    { label: "清除旧 mic 增益缓存", cmd: "adb shell rm -f /userdata/voice/.mic_gain" },
  ],
  p4: [
    { label: "⭐【验收】P4 看图+TTS", cmd: "bash /userdata/p4/scripts/p4_test.sh" },
    { label: "1828 显存预检", cmd: "bash /userdata/p4/scripts/p4_check_1828.sh" },
    { label: "仅 VLM（已有帧）", cmd: "bash /userdata/p4/scripts/vlm_see.sh /tmp/rtsp_latest.jpg" },
    { label: "仅 TTS 播报", cmd: "bash /userdata/p4/scripts/p4_tts.sh \"测试播报\"" },
    { label: "关闭 P4 TTS", cmd: "export P4_TTS=0 && bash /userdata/p4/scripts/p4_test.sh" },
    { label: "RTSP 帧 daemon", cmd: "bash /userdata/p4/scripts/rtsp_daemon.sh start" },
    { label: "RTSP daemon 状态", cmd: "bash /userdata/p4/scripts/rtsp_daemon.sh status" },
    { label: "PC 推送 P4 脚本", cmd: "powershell -File C:\\Users\\wwff\\Documents\\youyeetoo3588s\\p4\\push_p4.ps1" },
    { label: "设静态 IP", cmd: "bash /userdata/p4/scripts/net_static.sh" },
    { label: "RTSP 探测 h264/h265", cmd: "bash /userdata/p4/scripts/rtsp_probe.sh" },
    { label: "循环 3 轮", cmd: "bash /userdata/p4/scripts/p4_loop.sh 3" },
    { label: "仅取一帧", cmd: "bash /userdata/p4/scripts/rtsp_grab_once.sh /tmp/frame.jpg" },
    { label: "⚠️ voice 后跑 P4 前冷启动", cmd: "adb reboot && adb wait-for-device && sleep 45" },
  ],
  e2e: {
    asr: [
      { label: "⭐【ASR】咪头诊断（滴声+回放+ASR）", cmd: "bash /userdata/voice/scripts/mic_diag.sh 5" },
      { label: "【ASR】仅录音识别（输出文字）", cmd: "bash /userdata/voice/scripts/asr.sh" },
      { label: "【ASR】四路咪头路由探测", cmd: "python3 /userdata/voice/scripts/mic_probe.py" },
      { label: "【ASR】重听上次录音", cmd: "bash /userdata/voice/scripts/replay_last.sh" },
      { label: "【ASR】分析录音电平", cmd: "python3 /userdata/voice/scripts/analyze_wav.py /tmp/last_asr.wav" },
    ],
    tts: [
      { label: "⭐【TTS】喇叭滴声+合成测试", cmd: "bash /userdata/voice/scripts/speaker_test.sh" },
      { label: "【TTS】指定文字朗读", cmd: "bash /userdata/voice/scripts/tts.sh \"你好，这是一次测试播报\"" },
      { label: "【TTS】LLM 回复朗读（跳过录音）", cmd: "bash /userdata/voice/scripts/test_llm_tts.sh \"你好，请用一句话介绍你自己\"" },
    ],
    asrTts: [
      { label: "⭐【ASR→TTS】听写复读（无 LLM · P3.5 验收）", cmd: "bash /userdata/voice/scripts/asr_tts.sh" },
    ],
    voiceChat: [
      { label: "⭐【说话对话】ASR→LLM→TTS 循环", cmd: "bash /userdata/voice/scripts/voice_chat.sh" },
    ],
    seeSpeak: [
      { label: "⭐【看图说话】RTSP→VLM 描述→TTS 播报", cmd: "bash /userdata/p4/scripts/p4_test.sh" },
      { label: "【看图】1828 显存预检（必跑）", cmd: "bash /userdata/p4/scripts/p4_check_1828.sh" },
      { label: "【看图】仅 VLM 文字描述（已有帧）", cmd: "bash /userdata/p4/scripts/vlm_see.sh /tmp/rtsp_latest.jpg" },
      { label: "【看图】仅 TTS 播报描述", cmd: "bash /userdata/p4/scripts/p4_tts.sh \"画面里有一把椅子和一张桌子\"" },
      { label: "【看图】关闭 TTS 只看文字", cmd: "export P4_TTS=0 && bash /userdata/p4/scripts/p4_test.sh" },
    ],
    win: [
      { label: "Windows：ASR→TTS 一键", cmd: 'adb shell "bash /userdata/voice/scripts/asr_tts.sh"' },
      { label: "Windows：说话对话", cmd: 'adb shell "bash /userdata/voice/scripts/voice_chat.sh"' },
      { label: "Windows：看图说话", cmd: 'adb shell "bash /userdata/p4/scripts/p4_check_1828.sh && bash /userdata/p4/scripts/p4_test.sh"' },
      { label: "Windows：voice 后看图前先 reboot", cmd: "adb reboot && adb wait-for-device && timeout /t 45" },
      { label: "Windows：推送 voice 脚本", cmd: 'powershell -Command "Get-ChildItem C:\\Users\\wwff\\Documents\\youyeetoo3588s\\voice\\scripts\\*.sh,*.py | ForEach-Object { adb push $_.FullName /userdata/voice/scripts/ }; adb shell sed -i \'s/\\r$//\' /userdata/voice/scripts/*.sh; chmod +x /userdata/voice/scripts/*.sh"' },
      { label: "Windows：推送 P4 脚本", cmd: "powershell -File C:\\Users\\wwff\\Documents\\youyeetoo3588s\\p4\\push_p4.ps1" },
    ],
  },
  fan: [
    { label: "⭐【手动】设 PWM 200（约 78%）", cmd: "echo 200 > /sys/class/hwmon/hwmon0/pwm1 && sleep 0.2 && cat /sys/class/hwmon/hwmon0/pwm1" },
    { label: "【手动】低档 PWM 64（约 25%）", cmd: "echo 64 > /sys/class/hwmon/hwmon0/pwm1 && cat /sys/class/hwmon/hwmon0/pwm1" },
    { label: "【手动】满速 PWM 255", cmd: "echo 255 > /sys/class/hwmon/hwmon0/pwm1 && cat /sys/class/hwmon/hwmon0/pwm1" },
    { label: "【手动】停转 PWM 0", cmd: "echo 0 > /sys/class/hwmon/hwmon0/pwm1 && cat /sys/class/hwmon/hwmon0/pwm1" },
    { label: "确认 hwmon 名称", cmd: "cat /sys/class/hwmon/hwmon0/name" },
    { label: "确认 pwm-fan 已绑定", cmd: "ls -l /sys/devices/platform/pwm-fan/driver" },
    { label: "读 CPU 温度", cmd: "echo $(( $(cat /sys/class/thermal/thermal_zone0/temp) / 1000 ))C" },
    { label: "散热设备类型", cmd: "grep . /sys/class/thermal/cooling_device*/type" },
  ],
  fanVm: [
    { label: "VM 定位 DTS", cmd: "cd ~/kernel && grep -rn 'fan_ctrl\\|pwm-fan\\|&pwm6' arch/arm64/boot/dts/rockchip/*yyt*" },
    { label: "VM 编 kernel", cmd: "cd ~/kernel && export CROSS_COMPILE=../prebuilts/gcc/linux-x86/aarch64/gcc-arm-10.3-2021.07-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu- && make ARCH=arm64 rockchip_linux_defconfig rk3588_linux.config && make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE -j$(nproc) rk3588s-yyt.img" },
    { label: "VM 查 PWM_FAN", cmd: "grep CONFIG_PWM_FAN ~/kernel/.config" },
    { label: "Wiki 参考", cmd: "https://wiki.youyeetoo.com/en/r1/OUMISC#fan" },
    { label: "SDK 板级", cmd: "BoardConfig-R1-Ubuntu.mk · Docker docker-start.sh" },
    { label: "烧录", cmd: "RKDevTool 只勾 boot → zboot.img（~15MB）" },
  ],
  agent: [
    { label: "⭐【PC】推送 agent", cmd: "powershell -File C:\\Users\\wwff\\Documents\\youyeetoo3588s\\agent\\scripts\\push_agent.ps1" },
    { label: "⭐【安装】systemd + GUI + 壁纸", cmd: "adb shell sudo bash /userdata/agent/scripts/install_autostart.sh" },
    { label: "打开全屏 GUI", cmd: "bash /userdata/agent/scripts/open_agent_gui.sh" },
    { label: "信任桌面图标", cmd: "bash /userdata/agent/scripts/trust_desktop_launcher.sh youyeetoo" },
    { label: "设置科技风壁纸", cmd: "bash /userdata/agent/scripts/set_tech_wallpaper.sh youyeetoo" },
    { label: "放大桌面图标", cmd: "bash /userdata/agent/scripts/scale_desktop_icons.sh youyeetoo 128 2.25" },
    { label: "语音服务状态", cmd: "systemctl status r1-llm-daemon r1-orchestrator" },
    { label: "WS 探测", cmd: "python3 /userdata/agent/scripts/ws_probe.py" },
    { label: "GUI 日志", cmd: "tail -20 /userdata/agent/logs/gui_http.log" },
  ],
} as const;

const DIAG_COMPARE = [
  ["内核版本", "5.10.110 #12", "5.10.110 #12"],
  ["HugePages 160×32MB", "OK", "OK"],
  ["/dev/pcie-rkep-*", "存在", "存在"],
  ["EP inbound ATU", "bar2+0x2000 idx=3", "bar2+0x2000 idx=3 · 无重试"],
  ["rknn-smi Memory", "32 / 5120 MB", "36 / 5120 MB"],
  ["Chip Count", "1 · RK1828", "1 · RK1828"],
  ["Qwen3-0.6B Generate", "~155 tok/s", "~155 tok/s"],
  ["Qwen3-VL-4B Vision", "384² 通过", "384² 通过"],
  ["Qwen3-VL-4B LLM 文本", "~80 tok/s", "~80 tok/s"],
  ["Qwen3-VL-4B 端到端 VLM", "rknn_qwen3_vl_demo ✅", "rknn_qwen3_vl_demo ✅"],
  ["InternVL3.5-4B 端到端", "rknn_internvl3_demo ✅", "Vision 191ms ✅"],
  ["InternVL3.5-4B LLM 纯文本", "session_test ~80tok/s", "session_test ~80tok/s"],
  ["语音 MIC_ROUTE", "main_board v2 冻结", "peak~697 · prep 12x · ASR OK"],
  ["voice_chat / asr_tts", "ASR→TTS 验收", "✅ 2026-08-22 15:00 冻结"],
  ["P4 RTSP 取流", "640×480 tcp", "✅ h264 · ~2.5s"],
  ["P4 RTSP 描述", "InternVL 448²", "✅ 办公室场景"],
  ["模型版本", "v1.0.4", "v1.0.4（Runtime 1.0.5b10 兼容）"],
] as const;

function CommandBlock({ title, items }: { title: string; items: readonly { label: string; cmd: string }[] }) {
  return (
    <Stack gap={6}>
      <Text size="small" tone="secondary">{title}</Text>
      {items.map((item) => (
        <div key={item.label}>
          <Stack gap={2}>
            <Text size="small">{item.label}</Text>
            <Code>{item.cmd}</Code>
          </Stack>
        </div>
      ))}
    </Stack>
  );
}

const NODE_LABEL: Record<string, { title: string; sub: string }> = {
  mic: { title: "外接咪头", sub: "3588 · ES8388" },
  asr: { title: "ASR", sub: "3588 CPU · SenseVoice" },
  llm: { title: "RM1828 LLM", sub: "InternVL 纯文本" },
  tts: { title: "TTS", sub: "3588 CPU · VITS" },
  spk: { title: "左声道喇叭", sub: "Mono Left" },
  ipc: { title: "RTSP 摄像机", sub: "H.264/H.265" },
  decode: { title: "R1 硬解", sub: "RK3588S + MPP" },
  buffer: { title: "最新帧缓冲", sub: "1 槽，旧帧丢" },
  vlm: { title: "RM1828 VLM", sub: "448² · InternVL3.5-4B" },
  agent: { title: "Agent Runtime", sub: "聊天 / see()" },
};

function VoicePipelineGraph() {
  const theme = useHostTheme();
  const layout = useMemo(
    () =>
      computeDAGLayout({
        nodes: [{ id: "mic" }, { id: "asr" }, { id: "llm" }, { id: "tts" }, { id: "spk" }],
        edges: [
          { from: "mic", to: "asr" },
          { from: "asr", to: "llm" },
          { from: "llm", to: "tts" },
          { from: "tts", to: "spk" },
        ],
        direction: "horizontal",
        nodeWidth: 120,
        nodeHeight: 48,
        rankGap: 36,
        nodeGap: 20,
        padding: 8,
      }),
    [],
  );

  return (
    <svg width="100%" viewBox={`0 0 ${layout.width} ${layout.height}`} style={{ display: "block", maxWidth: layout.width }}>
      {layout.edges.map((e) => (
        <line
          key={`${e.from}-${e.to}`}
          x1={e.sourceX}
          y1={e.sourceY}
          x2={e.targetX}
          y2={e.targetY}
          stroke={theme.accent.primary}
          strokeWidth={1.25}
        />
      ))}
      {layout.nodes.map((n) => {
        const label = NODE_LABEL[n.id];
        return (
          <g key={n.id}>
            <rect x={n.x} y={n.y} width={120} height={48} rx={6} fill={theme.fill.secondary} stroke={theme.stroke.secondary} />
            <text x={n.x + 60} y={n.y + 20} textAnchor="middle" fill={theme.text.primary} fontSize={11} fontWeight={600}>
              {label.title}
            </text>
            <text x={n.x + 60} y={n.y + 36} textAnchor="middle" fill={theme.text.tertiary} fontSize={9}>
              {label.sub}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function VisionPipelineGraph() {
  const theme = useHostTheme();
  const layout = useMemo(
    () =>
      computeDAGLayout({
        nodes: [
          { id: "ipc" },
          { id: "decode" },
          { id: "buffer" },
          { id: "vlm" },
          { id: "agent" },
        ],
        edges: [
          { from: "ipc", to: "decode" },
          { from: "decode", to: "buffer" },
          { from: "buffer", to: "vlm" },
          { from: "vlm", to: "agent" },
          { from: "agent", to: "buffer" },
        ],
        direction: "horizontal",
        nodeWidth: 132,
        nodeHeight: 52,
        rankGap: 44,
        nodeGap: 28,
        padding: 8,
      }),
    [],
  );

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      style={{ display: "block", maxWidth: layout.width }}
    >
      {layout.edges.map((e) => (
        <line
          key={`${e.from}-${e.to}-${e.isBackEdge ? "back" : "fwd"}`}
          x1={e.sourceX}
          y1={e.sourceY}
          x2={e.targetX}
          y2={e.targetY}
          stroke={e.isBackEdge ? theme.stroke.primary : theme.accent.primary}
          strokeWidth={1.25}
          strokeDasharray={e.isBackEdge ? "4 3" : undefined}
        />
      ))}
      {layout.nodes.map((n) => {
        const label = NODE_LABEL[n.id];
        return (
          <g key={n.id}>
            <rect
              x={n.x}
              y={n.y}
              width={132}
              height={52}
              rx={6}
              fill={theme.fill.secondary}
              stroke={theme.stroke.secondary}
            />
            <text
              x={n.x + 66}
              y={n.y + 22}
              textAnchor="middle"
              fill={theme.text.primary}
              fontSize={11}
              fontWeight={600}
            >
              {label.title}
            </text>
            <text
              x={n.x + 66}
              y={n.y + 38}
              textAnchor="middle"
              fill={theme.text.tertiary}
              fontSize={10}
            >
              {label.sub}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function R1VlmAgentRoadmap() {
  const [phaseId, setPhaseId] = useCanvasState<string>("phase", "p36");
  const phase = PHASES.find((p) => p.id === phaseId) ?? PHASES[0];

  return (
    <Stack gap={24}>
      <Stack gap={8}>
        <H1>youyeetoo R1 + RM1828 对话看图智能体</H1>
        <Text tone="secondary">
          主机 R1（RK3588S · Ubuntu 22.04 · kernel 5.10.110 #12）。
          <strong>P0–P4 原型已全部跑通</strong>：语音对话（3588 ASR/TTS + 1828 LLM）+ RTSP 短看图（192.168.2.169）。
          下一步 <strong>P5 v1</strong>：llm_daemon 常驻流式 chat（2–4s 首响）· 并行 VLM spike → P5b。
        </Text>
      </Stack>

      <CollapsibleSection
        title="Canvas 永久保存说明"
        trailing={<Text size="small">本地文件 · 可备份</Text>}
      >
        <Stack gap={12}>
          <Callout tone="success" title="可以永久保存">
            Canvas 本质是磁盘上的普通文件，不依赖当前聊天会话。关闭 Cursor、换电脑拷贝文件、或
            git 提交后，内容都会保留。每次更新 Canvas 即更新该文件。
          </Callout>
          <Table
            headers={["方式", "说明", "推荐度"]}
            rows={[
              [
                "本地文件（默认）",
                CANVAS_PATH,
                "已生效 · 只要不删文件就一直在",
              ],
              [
                "手动备份",
                "复制 .canvas.tsx 到 U 盘 / 网盘 / Obsidian",
                "换机前建议做一次",
              ],
              [
                "Git 版本管理",
                "在项目目录 git init + commit；可回溯每次修改",
                "推荐 · 有完整历史 diff",
              ],
              [
                "Cursor 云端仓库",
                "对 Chat 说「帮我把项目保存到 Cursor 仓库」；非公开在线备份",
                "防丢盘 · 需 Cursor 账号",
              ],
              [
                "User Rules 记忆",
                "硬件/OS 锁定项已写入 Cursor Rules；Canvas 记实施细节",
                "互补 · 非 Canvas 替代",
              ],
            ]}
            striped
          />
          <Text size="small" tone="secondary">
            注意：Canvas 文件必须在 Cursor 项目的 canvases/ 目录下才能被 IDE
            识别为可视化面板。移走后仍可作为普通 TSX 文件保存，但需在 Cursor 内打开预览。
          </Text>
        </Stack>
      </CollapsibleSection>

      <Grid columns={5} gap={16}>
        <Stat value="P3.5 ✓" label="板载 voice_hw v2" tone="success" />
        <Stat value="P3.6 ✓" label="FY-SP701 --live" tone="success" />
        <Stat value="P4 ✓" label="RTSP→448² 短描述" tone="success" />
        <Stat value="P5 →" label="Agent 集成+设置 GUI" tone="warning" />
        <Stat value="1828" label="勿 voice+VLM 同占" tone="info" />
      </Grid>

      <Callout tone="success" title="当前里程碑（2026-08-21 23:16）">
        三大链路原型均已在板端验收：<strong>纯文本 LLM</strong> · <strong>语音对话</strong> · <strong>RTSP 短看图</strong>。
        延迟与 1828 <strong>LLM-only 常驻</strong>（Ollama 式）在 P5 v1 实现；看图 see() 经 spike 后 P5b 统一 vlm_daemon。
      </Callout>

      <Callout tone="success" title="P3.6 FY-SP701 验收（2026-08-28 · --live 11 PASS）">
        <strong>硬件</strong>：华芸 FY-SP701 V3 · USB cafe:b20a · <Code>plughw:1,0</Code> · 2MIC+5W功放。
        <strong>验收</strong>：<Code>bash /userdata/agent/scripts/phase_3_6_test.sh --live</Code>。
        <strong>下一步</strong>：Agent 采集/播放切 USB · GUI 设置 Modal · Streaming Paraformer 实机。
        模组 AEC/ANC/AGC 为固件黑盒；R1 ASR 走 Paraformer 流式，非模组文本 API。
      </Callout>

      <Callout tone="success" title="P3.5 验收冻结（2026-08-22 15:00 · voice_hw_board v2）">
        <strong>硬件</strong>：板载 MEMS + SH1.25 J368 GND+L/R stereo · 录音时勿插 3.5mm TRS。
        <strong>软件</strong>：gain=8 · prep_asr_wav · TTS 归一化 peak=26000。
        <strong>验收</strong>：<Code>asr_tts.sh</Code> 识别「请帮我解释什么是相对论」· TTS 播放完成。
        换麦 / RNNoise 降噪<strong>暂缓</strong>，后续再动。
      </Callout>

      <H2>P3.5 冻结参数（voice_hw_board.sh v2）</H2>
      <Table
        headers={["项", "值", "说明"]}
        rows={VOICE_HW_FROZEN.map((r) => [...r])}
        striped
      />

      <H2>P3.6 FY-SP701 参数与验收</H2>
      <Table
        headers={["项", "值", "说明"]}
        rows={P36_HW.map((r) => [...r])}
        striped
      />
      <Table
        headers={["验收项", "命令/条件", "实测", "状态"]}
        rows={P36_E2E_RESULTS.map((r) => [...r])}
        rowTone={[
          "success", "success", "success", "success", "success",
          "success", "success", "success", "warning", "warning",
        ]}
        striped
      />
      <Table
        headers={["算法", "位置", "P3.6 测试", "结论"]}
        rows={P36_ALGO_AUDIT.map((r) => [...r])}
        striped
      />

      <Callout tone="success" title="P3.5 标准测试入口">
        板端：<Code>bash /userdata/voice/scripts/asr_tts.sh</Code>（验收）·
        <Code>bash /userdata/voice/scripts/voice_chat.sh</Code>（含 LLM）·
        <Code>bash /userdata/p4/scripts/p4_test.sh</Code>（看图说话+TTS）。
        完整命令见下方 <strong>⑱ ASR · TTS · 看图说话</strong>。
      </Callout>

      <H2>⑱ ASR · TTS · 看图说话 — 三大验收命令</H2>
      <Callout tone="warning" title="测试前硬件 / 1828 须知">
        <strong>录音</strong>：板载 MEMS · J368 GND+L+R 喇叭 · 录音时<strong>勿插 3.5mm TRS</strong>。
        <strong>1828</strong>：<Code>voice_chat</Code>（LLM ~300MB）与 <Code>p4_test</Code>（VLM ~3GB）<strong>同 boot 不可混跑</strong>；
        跑 P4 前执行 <Code>p4_check_1828.sh</Code>，失败则 <Code>adb reboot</Code> 冷启后再测。
      </Callout>
      <Table
        headers={["链路", "说明", "板端命令", "通过判据", "备注"]}
        rows={E2E_THREE_FLOWS.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "info", "success", "warning"]}
        striped
      />
      <Grid columns={3} gap={16}>
        <Card>
          <CardHeader>ASR 识别</CardHeader>
          <CardBody>
            <CommandBlock title="" items={TEST_COMMANDS.e2e.asr} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>TTS 播报</CardHeader>
          <CardBody>
            <CommandBlock title="" items={TEST_COMMANDS.e2e.tts} />
            <Divider />
            <CommandBlock title="ASR→TTS" items={TEST_COMMANDS.e2e.asrTts} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>看图说话</CardHeader>
          <CardBody>
            <CommandBlock title="" items={TEST_COMMANDS.e2e.seeSpeak} />
            <Divider />
            <CommandBlock title="说话对话" items={TEST_COMMANDS.e2e.voiceChat} />
          </CardBody>
        </Card>
      </Grid>
      <CollapsibleSection title="⑱b Windows adb 一键（PC 端复制）" trailing={<Text size="small">无需进 shell</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.e2e.win} />
      </CollapsibleSection>
      <CollapsibleSection title="⑱c 板端整段复制（adb shell 内）" trailing={<Text size="small">三大验收</Text>}>
        <Code>{`# === 硬件：J368 喇叭 · 板载麦 · 勿插 3.5mm TRS ===

# --- ① ASR 单测 ---
bash /userdata/voice/scripts/mic_diag.sh 5
# 预期：peak 500–3000 · [ASR] 中文非空

# --- ② TTS 单测 ---
bash /userdata/voice/scripts/speaker_test.sh
bash /userdata/voice/scripts/tts.sh "你好，这是一次测试播报"
# 预期：peak=26000 · ch=2 · 播放完成

# --- ③ ASR→TTS 听写复读（⭐ P3.5 验收 · 无 LLM）---
bash /userdata/voice/scripts/asr_tts.sh
# 预期：[HW] 冻结配置 v2 · 说中文 → 同句 TTS 朗读

# --- ④ 说话对话 ASR→LLM→TTS ---
bash /userdata/voice/scripts/voice_chat.sh
# 回车录音 · Intern-S1 回答 · J368 朗读 · Ctrl+C 退出

# --- ⑤ 看图说话 RTSP→VLM→TTS（⭐ P4 验收）---
# 若刚跑过 voice_chat：先 adb reboot && sleep 45
bash /userdata/p4/scripts/p4_check_1828.sh
bash /userdata/p4/scripts/p4_test.sh
# 预期：RTSP 取帧 · 中文画面描述 · [P4-TTS] J368 播报 peak=26000`}</Code>
      </CollapsibleSection>

      <Callout tone="warning" title="P3.5 延迟瓶颈与优化路线">
        当前为<strong>批处理原型</strong>：固定 5s 录音 + 离线 ASR/TTS + 每轮 LLM 冷 patch。
        正式版 SDK <Code>llm_chat</Code> 可消除 LLM patch 并常驻 Session（省 ~1s/轮，首轮仍 ~60s）。
        ASR/TTS 延迟需改架构：<strong>流式 ASR + VAD 端点</strong>、<strong>TTS 流式/分句</strong>、跳过 debug 回放。
        1828 RKNN3 ASR/TTS 为远期选项（现架构 1828 专供 LLM）。
      </Callout>

      <Callout tone="success" title="硬件验收通过（P0 + P1 · 2026-08-21）">
        冷启动 rknn-smi <strong>36 / 5120 MB</strong>、Chip Count 1、RK1828 Health OK。
        kernel #12 ATU 稳定无重试。RM1828 可正常加载 4B 级模型并推理——硬件链路无问题。
      </Callout>

      <Callout tone="success" title="P1 LLM 冒烟（Qwen3-0.6B v1.0.4）">
        Prefill ~500 tok/s、Generate ~155 tok/s。路径 /userdata/models/Qwen3-0.6B/。
      </Callout>

      <Callout tone="success" title="P2 InternVL3.5-4B 端到端通过（2026-08-21 21:57）">
        <Code>rknn_internvl3_demo</Code> 448² · Vision <strong>191 ms</strong> · Prefill ~625 tok/s。
        输出正确描述 demo.jpg。thinking 已在 demo 内关闭（enable_thinking=false）。
      </Callout>

      <Callout tone="success" title="P3 纯文本 LLM 通过（2026-08-21 22:00）">
        纯聊天用 <Code>rknn3_session_test</Code> 仅加载 llm 四件套，<strong>不加载 vision</strong>。
        1024 ctx · 中英文双 prompt · Generate ~80 tok/s · 显存 ~236MB（vs VLM ~3GB+）。
        交互式多轮 Agent 留 P5；本关验证 LLM 主干可独立推理。
      </Callout>

      <Callout tone="success" title="P3 Session 板端复验（2026-08-22 15:28 · 无需 VM 编译）">
        <strong>结论</strong>：测 Session / 流式 token <strong>不需要改 C++ 源码</strong>，板端已有
        <Code>/usr/bin/rknn3_session_test</Code>，adb 直接跑即可。
        <strong>TEST1</strong> stock：Prefill 123ms · 162 tok/s · Generate 855ms · 74 tok/s（64 tok）。
        <strong>TEST2</strong> <Code>llm_ask.py</Code>：「你好…」→ Intern-S1 自我介绍 · ~28s。
        仅 push 了 <Code>llm_ask.py</Code> + <Code>test_llm_tts.sh</Code>；P5 改源码做 <Code>llm_chat</Code> 常驻时才需 VM 交叉编译。
      </Callout>

      <Callout tone="success" title="P4 RTSP 看图通过（2026-08-22 更新）">
        <Code>p4_test.sh</Code>：RTSP 取帧 → InternVL 短描述 → <Code>p4_tts</Code> J368 播报。
        Vision ~190 ms · 整轮 ~30 s（stock demo 冷加载）。<Code>p4_check_1828</Code> 预检显存。
        P5 目标：<strong>按需</strong>看图（「看看」触发 · VLM 热待机 ~2s），非全时 1fps 轮询。
      </Callout>

      <Callout tone="warning" title="1828 资源互斥 → P5 按需调度">
        现状：<Code>voice_chat</Code>（LLM-only ~300MB）与 VLM（~3GB）<strong>不可同占</strong> 1828。
        原型：切换模式需 <Code>adb reboot</Code>；<Code>p4_check_1828.sh</Code> 在显存 &gt;80MB 时提前拒绝。
        P5 目标：<strong>chat ↔ see 按需快速切换</strong>（unload/warm-swap · 免冷启 · 用户说「看看」秒级响应）。
      </Callout>

      <Callout tone="info" title="重要：验收方式">
        用 <strong>adb reboot 冷启动</strong> 让 systemd 拉起 rknn3.service，不要手动
        rknn3_startup restart（会触发 Re-Init · bar2_phy=0 · Memory NA）。
      </Callout>

      <Callout tone="neutral" title="技术模型（R1 + RM1828）">
        共享内存路径：主机 hugepage CPU 地址 → <strong>EP inbound ATU</strong>（bar2 mmap +
        0x2000），非 RK3588 RC inbound。bar4+0x300000 超时 -110 属预期。check ddr load addr
        来自 pcie_upgrade_tool ELBI，非 rknn-smi 运行时路径。
      </Callout>

      <Table headers={["层级", "状态", "证据"]} rows={STATUS_LAYERS.map((r) => [...r])} striped />

      <H2>P4 RTSP 实测（2026-08-21 23:15）</H2>
      <Table
        headers={["配置项", "值", "说明"]}
        rows={P4_CONFIG.map((r) => [...r])}
        striped
      />
      <Table
        headers={["环节", "条件", "实测", "结果"]}
        rows={P4_E2E_RESULTS.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "success", "warning", "warning"]}
        striped
      />

      <H2>㉑ P5 智能体 — TECH_PLAN v1.0（2026-08-26 锁定）</H2>
      <Callout tone="success" title="路径：Ollama 式 LLM-only daemon → 并行 VLM spike → P5b 统一 vlm_daemon">
        v1 1828 常驻 <strong>InternVL3.5-4B LLM-only 四件套</strong>（~236MB · 不加载 vision）。
        3588：VAD + sherpa ASR/TTS（<strong>CPU</strong>）+ asyncio 编排。
        see() 不在 v1；并行 spike S1–S3，通过后 P5b 用统一 <Code>vlm_daemon</Code> 替换 <Code>llm_daemon</Code>，非长期双模型。
        文档：<Code>agent/docs/TECH_PLAN.md</Code> · 代码库 <Code>youyeetoo3588s/agent/</Code>
      </Callout>
      <Table
        headers={["项", "规格", "说明"]}
        rows={P5_LLM_DAEMON_MODEL.map((r) => [...r])}
        rowTone={[
          "info", "success", "neutral", "neutral",
          "neutral", "neutral", "neutral", "neutral",
          "neutral", "success", "success", "info", "info",
        ]}
        striped
      />
      <Table
        headers={["阶段", "交付", "验收", "状态"]}
        rows={P5_IMPL_PHASES.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "success", "warning", "neutral"]}
        striped
      />
      <H3>HDMI 桌面 GUI（2026-08-27）</H3>
      <Table
        headers={["项", "路径 / 端口", "说明"]}
        rows={P5_DESKTOP_GUI.map((r) => [...r])}
        rowTone={["info", "neutral", "neutral", "warning", "success", "success", "success", "neutral", "success"]}
        striped
      />
      <Table
        headers={["决策", "选定", "日期"]}
        rows={P5_DECISIONS_LOCKED.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "success", "success", "success"]}
        striped
      />
      <CollapsibleSection title="㉑a llm_daemon 启动等价命令" trailing={<Text size="small">P3 已验收 · fork 为 daemon</Text>}>
        <Code>{`# 1828 常驻 · InternVL3.5-4B LLM-only（不加载 vision）
/userdata/agent/bin/llm_daemon \\
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.rknn \\
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.weight \\
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.tokenizer.gguf \\
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.embed.bin \\
  1024 64 0xff

# 客户端（Phase A 验收）
/userdata/agent/bin/llm_client --prompt "你好" --stream

# 提示词（不改权重）
/userdata/agent/config/agent.yaml`}</Code>
      </CollapsibleSection>

      <H2>P5 1828 演进与 spike</H2>
      <Table
        headers={["项", "设计", "说明"]}
        rows={P5_1828_SCHEDULER.map((r) => [...r])}
        striped
      />

      <H2>P5 下一步</H2>
      <Table headers={["方向", "内容", "备注"]} rows={NEXT_MILESTONES.map((r) => [...r])} striped />

      <H2>P3.5 语音 E2E 实测（验收 2026-08-22 15:00）</H2>
      <Table
        headers={["环节", "输入 / 条件", "实测", "结果"]}
        rows={VOICE_E2E_RESULTS.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "success", "neutral"]}
        striped
      />

      <H2>P3.5 验收标准（asr_tts.sh）</H2>
      <Table
        headers={["项", "条件", "通过判据"]}
        rows={VOICE_ACCEPTANCE.map((r) => [...r])}
        striped
      />

      <H2>语音延迟分解与优化</H2>
      <Table
        headers={["环节", "当前实现", "典型耗时", "瓶颈", "优化方向"]}
        rows={VOICE_LATENCY.map((r) => [...r])}
        striped
      />
      <UsageBar
        total={15000}
        topLeftLabel="当前一轮对话预算（原型）：约 12–15 s"
        topRightLabel="5s 录音 + 2s ASR + 2s LLM + 3s TTS + 回放"
        segments={[
          { id: "record", value: 5000, color: "blue" },
          { id: "asr", value: 2000, color: "gray" },
          { id: "llm", value: 2000, color: "orange" },
          { id: "tts", value: 3000, color: "green" },
          { id: "replay", value: 3000, color: "gray" },
        ]}
      />
      <Text size="small" tone="secondary">
        优化后目标：VAD 端点 + 流式 ASR → 说完 ~1s 出文字；LLM 常驻 → 后续轮 ~1s；流式 TTS → 首音 &lt;500ms。
        正式 llm_chat 不解决 ASR/TTS 架构延迟，需 P5 流式管线。
      </Text>

      <H2>P2/P3 推理实测（InternVL3.5-4B · 2026-08-21）</H2>
      <Table
        headers={["组件", "工具", "配置", "Prefill", "Generate/Vision", "结果"]}
        rows={VLM_INFERENCE_RESULTS.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "success", "success"]}
        striped
      />

      <H2>P3 纯文本 LLM（rknn3_session_test · 无 vision）</H2>
      <Table
        headers={["测试", "输入", "Prefill", "Prefill TPS", "Generate", "Generate TPS"]}
        rows={P3_INFERENCE_RESULTS.map((r) => [...r])}
        striped
      />
      <H3>P3 Session 板端复验（2026-08-22 · adb 直测）</H3>
      <Table
        headers={["方式", "条件", "Prefill / 输出", "Generate / 耗时", "结果"]}
        rows={P3_SESSION_REVERIFY.map((r) => [...r])}
        rowTone={["success", "success", "neutral", "success"]}
        striped
      />
      <Text size="small" tone="secondary">
        纯文本路径只加载 llm .rknn + .weight + tokenizer + embed；显存 ~236MB。
        rknn_internvl3_demo 始终加载 vision，不可用于纯聊天。
        SDK 参考 demo：<Code>rknn3_session_test_demo/</Code>（PC 仓库仅部分文件 · 完整目录在 RK1820_1828_RELEASE_V1.0.5B10）。
      </Text>

      <H2>P1 推理实测（Qwen3-0.6B v1.0.4）</H2>
      <Table
        headers={["测试", "输入", "Prefill", "Prefill TPS", "Generate", "Generate TPS"]}
        rows={INFERENCE_RESULTS.map((r) => [...r])}
        striped
      />

      <H2>测试命令速查（可复制）</H2>

      <CollapsibleSection title="⑨ Windows / adb 连接" trailing={<Text size="small">PC 端</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.adb} />
      </CollapsibleSection>

      <CollapsibleSection title="⑩ 板端环境 / PCIe / ATU 验收" trailing={<Text size="small">adb shell</Text>}>
        <Stack gap={16}>
          <CommandBlock title="环境与驱动" items={TEST_COMMANDS.env} />
          <Divider />
          <CommandBlock title="内核 ATU（kernel #12）" items={TEST_COMMANDS.atu} />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="⑪ rknn-smi / 服务验收" trailing={<Text size="small">冷启动优先</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.rknn} />
      </CollapsibleSection>

      <CollapsibleSection title="⑫ 模型下载与推送" trailing={<Text size="small">Windows → 板端</Text>}>
        <Stack gap={12}>
          <Table
            headers={["文件", "说明"]}
            rows={[
              ["Qwen3-0.6B.rknn", "模型结构 · 23 MB"],
              ["Qwen3-0.6B.weight", "权重 · 370 MB"],
              ["Qwen3-0.6B.tokenizer.gguf", "分词器 · 5.7 MB"],
              ["Qwen3-0.6B.embed.bin", "嵌入层 · 297 MB"],
            ]}
            striped
          />
          <CommandBlock title="" items={TEST_COMMANDS.modelWin} />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="⑬ LLM 推理冒烟（P1）" trailing={<Text size="small">Qwen3-0.6B</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.infer} />
      </CollapsibleSection>

      <CollapsibleSection title="⑬b Qwen3-VL-4B 分项 / VLM 测试（P2）" trailing={<Text size="small">adb shell</Text>}>
        <Stack gap={12}>
          <Table
            headers={["文件", "大小"]}
            rows={[
              ["vision_Qwen3-VL-4B.rknn + .weight", "4.2M + 234M"],
              ["llm_Qwen3-VL-4B.rknn + .weight", "25M + 2.3G"],
              ["Qwen3-VL-4B.tokenizer.gguf", "5.7M"],
              ["Qwen3-VL-4B.embed.bin", "742M"],
            ]}
            striped
          />
          <CommandBlock title="" items={TEST_COMMANDS.vlm} />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="⑬c P3 纯文本 LLM 测试（InternVL · adb shell）" trailing={<Text size="small">无 vision</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.p3} />
      </CollapsibleSection>

      <CollapsibleSection title="⑭ 刷机 / 内核更新" trailing={<Text size="small">RKDevTool</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.flash} />
      </CollapsibleSection>

      <CollapsibleSection title="⑭b P5 Agent · HDMI GUI" trailing={<Text size="small">agent/</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.agent} />
      </CollapsibleSection>

      <CollapsibleSection title="⑮ 一键验收脚本（复制整段）" trailing={<Text size="small">adb shell</Text>}>
        <Code>{`# === P1 完整验收（冷启动后执行）===
uname -r
zcat /proc/config.gz | grep -E 'PCIE_FUNC_RKEP|HUGETLBFS'
grep -iE 'Huge|Hugetlb' /proc/meminfo
lspci | grep 182a
ls -l /dev/pcie-rkep-*
dmesg | grep -i 'BAR2 inbound'
dmesg | grep -ci 'all paths failed'
systemctl is-active rknn3.service
rknn-smi -v
rknn-smi info
rknn-smi info -l

# === P1 推理（模型已推送后）===
cd /userdata/models/Qwen3-0.6B
rknn3_session_test Qwen3-0.6B.rknn Qwen3-0.6B.weight \\
  Qwen3-0.6B.tokenizer.gguf Qwen3-0.6B.embed.bin 1024 256 0xff`}</Code>
        <Divider />
        <Code>{`# === P3 Session 复验（adb shell · 无需 VM 编译）===
cd /userdata/models/InternVL3_5-4B
/usr/bin/rknn3_session_test \\
  llm_InternVL3_5-4B.rknn llm_InternVL3_5-4B.weight \\
  InternVL3_5-4B.tokenizer.gguf InternVL3_5-4B.embed.bin \\
  1024 64 0xff
# 预期：相对论解释 · Prefill ~160 tok/s · Generate ~74 tok/s

python3 /userdata/voice/scripts/llm_ask.py '你好，请用一句话介绍你自己'
# 预期：Intern-S1 自我介绍 · ~28s`}</Code>
        <Divider />
        <Code>{`# === P3.5 语音验收（adb shell · 2026-08-22 冻结）===
# 硬件：J368 GND+L+R 喇叭 · 勿插 3.5mm TRS · 板载麦
bash /userdata/voice/scripts/asr_tts.sh
# 预期：[HW] 冻结配置 v2 · gain=8 · normalize→26000
# 预期：peak 500–3000 · [ASR] 中文短句 · [play] peak=26000 · [TTS] 播放完成

# 含 LLM 全链路：
bash /userdata/voice/scripts/voice_chat.sh

# 诊断 / 探测：
bash /userdata/voice/scripts/mic_diag.sh 5
python3 /userdata/voice/scripts/mic_probe.py
bash /userdata/voice/scripts/speaker_test.sh`}</Code>
        <Divider />
        <Code>{`# === P4 看图验收（adb shell · 勿与 voice_chat 同 boot）===
# 若刚跑过 voice_chat 或 VLM 失败：先 adb reboot
bash /userdata/p4/scripts/p4_check_1828.sh
bash /userdata/p4/scripts/p4_test.sh
# 预期：VLM 中文描述 · [P4-TTS] 播报 · peak=26000

# 仅看图 / 仅播报：
bash /userdata/p4/scripts/vlm_see.sh /tmp/rtsp_latest.jpg
bash /userdata/p4/scripts/p4_tts.sh "测试播报"`}</Code>
        <Divider />
        <Code>{`# === P5 Agent + HDMI GUI（adb shell）===
sudo bash /userdata/agent/scripts/install_autostart.sh
systemctl status r1-llm-daemon r1-orchestrator
bash /userdata/agent/scripts/open_agent_gui.sh
# 预期：Chromium 全屏 http://127.0.0.1:8766/ · WS 已连接 · 对着麦说话有状态变化

python3 /userdata/agent/scripts/ws_probe.py`}</Code>
      </CollapsibleSection>

      <H2>完整时间线（可折叠查阅）</H2>

      <CollapsibleSection
        title="① 方案设计与锁定决策（2026-08-21 上午）"
        trailing={<Text size="small">11:25–11:57</Text>}
      >
        <Stack gap={12}>
          <Table
            headers={["时间", "事项", "结论 / 动作"]}
            rows={[
              ["11:25", "立项", "端侧对话智能体 + RM1828；初以为 YY3588 板"],
              ["11:27", "VLM 选型", "原生 VLM 优于 LLM+检测拼接；RM1828 跑 3B/4B 甜点"],
              ["11:32", "InternVL3.5-4B", "可纯对话（Qwen3-4B 主干）；RTSP 1fps 可行但仅短描述"],
              ["11:34", "实施路线", "P0–P6 分关；Canvas 路线图创建"],
              ["11:52", "Debian 重编?", "拒绝 R1 Dcompile；不编 Debian 11/12"],
              ["11:54", "硬件更正", "实际板子 youyeetoo R1 SBC（RK3588S），非 YY3588"],
              ["11:57", "系统锁定", "决定烧官方 Ubuntu 22.04 img；Wiki burnemmc"],
            ]}
            striped
          />
          <H3>锁定决策（仍有效）</H3>
          <Table
            headers={["项", "内容"]}
            rows={[
              ["主机", "youyeetoo R1 · RK3588S · 100×69.3mm"],
              ["加速卡", "RM1828 / RK1828 · M.2 M-Key · 独立 12V · 20TOPS · 5GB"],
              ["工具链", "RKNN3（非 RKNN-Toolkit2 / RKLLM 跑 RM1828）"],
              ["模型", "InternVL3.5-4B-Instruct · W4A16 · 448² · thinking 关"],
              ["视觉输入", "RTSP TCP · 按需看图 · P5 热待机 ~2s"],
              ["语音", "3588 ASR/TTS + 1828 LLM · voice_hw_board v2 冻结 · 换麦暂缓"],
            ]}
            striped
          />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="② P0 烧录与硬件（2026-08-21 中午）"
        trailing={<Text size="small">12:09–14:12 · 已完成</Text>}
      >
        <Stack gap={12}>
          <Table
            headers={["问题 / 动作", "处理"]}
            rows={[
              ["Recovery 不识别", "V3 拨码 DEVICE；USB-A 公对公；先插线再上电按 Recovery"],
              ["Recovery vs Boot", "Recovery=刷机 loader；Boot=从 eMMC/TF 正常启动"],
              ["官方固件", "http://dd.youyeetoo.cn:5000/sharing/ymaoRMfUe · 百度 1234"],
              ["烧录工具", "Windows RKDevTool + RK USB 驱动 · wiki burnemmc"],
              ["V2 接线", "Type-C OTG · Recovery 上电 2–3s"],
              ["V3 接线", "USB-A · 背面 M.2 2280"],
              ["2024-04-01 前板", "背面无 QR 需先跑售后配置工具"],
              ["烧录结果", "Ubuntu 22.04 · kernel 5.10.110 · adb shell OK"],
              ["PCIe 枚举", "lspci 0003:31:00.0 Device 182a"],
            ]}
            striped
          />
          <Text size="small" tone="secondary">
            登录 youyeetoo / 123456 · 桌面自动登录 · root 默认无密码。
          </Text>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="③ P1 RKNN3 安装与 pcie-rkep 诊断（2026-08-21 下午）"
        trailing={<Text size="small">14:12–14:31</Text>}
      >
        <Stack gap={12}>
          <Table
            headers={["步骤", "现象", "结论"]}
            rows={[
              ["安装包", "rknpu_rk182x_m2_v1.0.5b10_installer_arm64.tgz", "install.sh 成功 · rknn3.service 启用"],
              ["重启后", "rknn-smi -v → Failed to initialize rknnsmi", "非时序 · 驱动缺失"],
              ["journal", "failed to get pcie-rkep.ko · Failed to load driver", "根因起点"],
              ["/lib/modules", "不存在 · 安装包 clean unless files 删了解压目录", "R1 Ubuntu 无模块树"],
              ["安装包内", "tar -tzf 无 pcie-rkep.ko", "驱动不在 userspace 包 · 须内核内置"],
              ["/proc/config.gz", "CONFIG_PCIE_FUNC_RKEP 未开", "官方镜像缺 RKEP"],
              ["/dev/pcie-rkep-*", "不存在", "与上一致"],
              ["rknn3_startup 逻辑", "find /lib/modules pcie-rkep.ko → insmod → pcie_upgrade_tool 刷 FW", "驱动是第一关"],
            ]}
            striped
          />
          <Callout tone="warning" title="关键认知">
            lspci 见 182a 只说明 PCIe 枚举成功，不等于 RKNN3 能通信。必须
            pcie-rkep 驱动 + /dev/pcie-rkep-* + Re-Init 成功才有 Memory 5120MB。
          </Callout>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="④ 编译环境搭建（3588buildsdk VM）"
        trailing={<Text size="small">14:31–16:00+</Text>}
      >
        <Stack gap={12}>
          <Table
            headers={["项", "配置"]}
            rows={[
              ["SSH", "gp@192.168.100.196 · Host 3588buildserver"],
              ["宿主", "PVE VM104 · Debian 13 · x86_64"],
              ["SDK", "~/project/R1_SDK · 从 Windows SCP（gz 分包）· 勿下 22G dl.tar.gz"],
              ["Docker", "docker.io · R1 SDK ./docker/docker-start.sh → Ubuntu 20.04 容器"],
              ["代理", "192.168.100.176:7890（Clash mixed-port）"],
              ["apt 陷阱", "/etc/apt/apt.conf 旧 192.168.100.3:7899 需删 · 保留 99proxy 176:7890"],
              ["Cursor SSH", "cursor-server 本地下载 SCP · ~/.wgetrc 代理"],
              ["RK182X SDK", "~/rk182x_sdk/ · pcie-rkep.c 源 · V1.0.5B10"],
            ]}
            striped
          />
          <Text size="small" tone="secondary">
            编内核走 R1 Ucompile（BoardConfig-R1-Ubuntu.mk），不是 Dcompile / YY3588
            CompileSource。
          </Text>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="⑤ 内核集成 pcie-rkep + HugePage（编译 VM）"
        trailing={<Text size="small">16:00–18:20</Text>}
      >
        <Stack gap={12}>
          <Table
            headers={["工作项", "状态", "备注"]}
            rows={[
              ["drivers/misc/rockchip/pcie-rkep.c", "已合并", "PCI ID 182a · RK182X SDK"],
              ["CONFIG_PCIE_FUNC_RKEP=y", "已开", "验收 zcat /proc/config.gz"],
              ["CONFIG_PCIE_DW_DMATEST=y", "已开", "DMA 测试"],
              ["CONFIG_PCIEASPM_EXT", "已禁用", "R1 5.10 缺 ASPM API · 编不过"],
              ["CONFIG_HUGETLBFS=y", "已开", "RM1828 BAR2 DDR 映射需要"],
              ["CONFIG_HUGETLB_PAGE=y", "已开", "同上"],
              ["dmatest Makefile", "已修", "路径 + rk_pcie->pci->dev"],
              ["boot.img 过大", "改 zboot.img", "RKDevTool force write boot 分区"],
              ["DTS bootargs", "hugepages=16→160", "default_hugepagesz=32M hugepagesz=32M"],
              ["刷机后", "/dev/pcie-rkep-0003:31:00.0 OK", "rknn-smi Driver 3.3.1"],
            ]}
            striped
          />
          <H3>编内核产出路径</H3>
          <Text>
            <Code>~/kernel/zboot.img</Code>
            {" → RKDevTool 只烧 boot 分区 · 勿整包重刷 eMMC"}
          </Text>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="⑥ BAR2 / HugePage 调试与 adb 实测"
        trailing={<Text size="small">18:20–18:52</Text>}
      >
        <Stack gap={12}>
          <Table
            headers={["检查项", "正常", "当前 R1"]}
            rows={DIAG_COMPARE.map((r) => [...r])}
            rowTone={DIAG_COMPARE.map((r) =>
              r[1] === r[2] ? "success" : "danger",
            )}
            striped
          />
          <Divider />
          <H3>adb 测试（已全部执行 · 均排除）</H3>
          <Table
            headers={["测试", "命令 / 条件", "结果"]}
            rows={[
              ["HugePage 确认", "grep HugePages /proc/meminfo", "160×32768kB · hugetlbfs 已挂"],
              ["延时 startup", "proxy 15s → rknn3_startup start", "Re-Init 仍失败 · bar2=0"],
              ["二次 retry", "sleep 30 → startup", "同上"],
              ["固件 MD5", "ext-m2 vs rk1820.img", "1ebd4387… 完全相同"],
              ["debug 日志", "TRANSFER_LOG_LEVEL=debug", "无额外 bar2 细节"],
              ["console", "rknn-console rk1820 -d 0", "VUART magic error · EP 未就绪"],
              ["dmesg", "alloc_contig_range PFNs busy", "4ffa00000 CMA 冲突 · 次要"],
              ["transfer_proxy 字符串", "failed, no bar2 memory · mmap bar2 failed", "userspace 路径确认"],
            ]}
            striped
          />
          <Callout tone="danger" title="根因（2026-08-21 18:52 确认）">
            lspci BAR2=0x9c0000000 硬件正常，但 obj_info→ep_bar2_phy_addr 始终 0。
            驱动 probe 未写入 pci_resource_start(dev,2)。HugePage/固件/时序均非根因。
          </Callout>
          <H3>startup 典型日志片段</H3>
          <Text size="small">
            <Code>
              bar2 bar2_phy_addr=0x0 → Device boot state success:1 → Re-Init → check
              ddr load addr request failed → Device request state: 0xffa70000
            </Code>
          </Text>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="⑦ P1/P2/P3 完成 · 错误记录"
        trailing={<Text size="small">P3 LLM-only ✅ · P4 RTSP 待做</Text>}
      >
        <Stack gap={12}>
          <H3>P1 已完成</H3>
          <Table
            headers={["项", "结果"]}
            rows={[
              ["kernel #12 zboot", "ATU bar2+0x2000 · 无重试 · 冷启动 5120MB"],
              ["rknn3.service", "active · 勿手动 restart"],
              ["Qwen3-0.6B 推理", "v1.0.4 · ~155 tok/s · /userdata/models/"],
            ]}
            striped
          />
          <H3>P2/P3 已完成（InternVL3.5-4B）</H3>
          <Table
            headers={["项", "状态 / 动作"]}
            rows={[
              ["InternVL 模型", "✅ /userdata/models/InternVL3_5-4B/ · 3.3GB"],
              ["InternVL 端到端 VLM", "✅ rknn_internvl3_demo · Vision 191ms"],
              ["InternVL LLM 纯文本", "✅ session_test · ~80 tok/s · 236MB"],
              ["纯聊天路径", "session_test 仅 llm；勿用 internvl3_demo"],
              ["下一步 P4", "RTSP 1fps · GStreamer + 448² 短描述"],
              ["DTS 持久化", "hugepages=160 写入 rk3588s-yyt.dts bootargs"],
            ]}
            striped
          />
          <H3>已解决错误（完整）</H3>
          <Table
            headers={["错误", "修复"]}
            rows={[
              ["CONFIG_PCIEASPM_EXT 编不过", "禁用 · R1 5.10 无 rockchip pcie ASPM API"],
              ["dmatest 重复符号", "修正 Makefile 路径"],
              ["boot.img 超分区", "改用 zboot.img force write"],
              ["/usr/lib/modules 不存在", "内核内置 pcie-rkep · 不依赖 insmod 外置 ko"],
              ["obj_info ep_bar2 未写入", "probe + SYNC 补丁写 ep_bar2_phy_addr"],
              ["bar2_phy=0 · Chip Count 0", "EP inbound ATU bar2+0x2000 → hugepage cpu=0x4fa000000"],
              ["ATU 读回 0xffffffff 误判", "kernel #12：写入成功即 done · 停 10s 重试"],
              ["手动 rknn3_startup restart 失败", "用冷启动 + systemd · 勿 Re-Init"],
              ["代理 7899 连不上", "删 apt.conf 旧代理 · 用 176:7890"],
              ["Cursor SSH 下载超时", "本地下载 cursor-server SCP 到 VM"],
            ]}
            striped
          />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection
        title="⑧ 板端命令速查（历史 · 见 ⑨–⑮ 完整版）"
        trailing={<Text size="small">adb shell</Text>}
      >
        <Text size="small" tone="secondary">
          完整测试命令已移至上方 ⑨–⑮ 折叠区。以下为早期积累的最小集。
        </Text>
        <Stack gap={8}>
          <Text size="small" tone="secondary">P0 / 环境</Text>
          <Text><Code>cat /etc/os-release && uname -r</Code></Text>
          <Text><Code>lspci | grep -i 182</Code></Text>
          <Divider />
          <Text size="small" tone="secondary">P1 驱动 / 配置</Text>
          <Text><Code>zcat /proc/config.gz | grep -E PCIE_FUNC_RKEP|HUGETLB</Code></Text>
          <Text><Code>ls -l /dev/pcie-rkep-*</Code></Text>
          <Text><Code>grep -i huge /proc/meminfo</Code></Text>
          <Divider />
          <Text size="small" tone="secondary">P1 验收（推荐冷启动）</Text>
          <Text><Code>adb reboot && adb wait-for-device && sleep 45</Code></Text>
          <Text><Code>rknn-smi -v && rknn-smi info && rknn-smi info -l</Code></Text>
          <Divider />
          <Text size="small" tone="secondary">P1 推理</Text>
          <Text><Code>cd /userdata/models/Qwen3-0.6B && rknn3_session_test Qwen3-0.6B.rknn Qwen3-0.6B.weight Qwen3-0.6B.tokenizer.gguf Qwen3-0.6B.embed.bin 1024 256 0xff</Code></Text>
        </Stack>
      </CollapsibleSection>

      <H2>当前状态摘要</H2>
      <Table
        headers={["检查项", "期望", "当前 R1"]}
        rows={DIAG_COMPARE.map((r) => [...r])}
        rowTone={DIAG_COMPARE.map((r) =>
          r[2].includes("失败") ? "danger" : r[1] === r[2] || r[2].includes("通过") ? "success" : "warning",
        )}
        striped
      />

      <BarChart
        categories={["HugePage", "pcie-rkep", "EP ATU", "5120MB", "InternVL VLM", "InternVL LLM", "Voice I/O", "RTSP", "Agent"]}
        series={[{ name: "完成度 %", data: [100, 100, 100, 100, 100, 100, 92, 90, 58], tone: "info" }]}
        height={180}
        valueSuffix="%"
        yMax={100}
      />

      <H2>进度日志（完整）</H2>
      <Table
        headers={["日期时间", "阶段", "记录"]}
        rows={PROGRESS_LOG.map((r) => [r.date, r.item, r.detail])}
        striped
      />

      <H2>内核补丁清单（#12 当前运行）</H2>
      <Table
        headers={["项", "状态 / 说明"]}
        rows={[
          ["CONFIG_PCIE_FUNC_RKEP=y", "已开 · 内置 pcie-rkep"],
          ["CONFIG_HUGETLBFS + HUGETLB_PAGE", "已开"],
          ["bootargs hugepages=160", "运行时 OK · DTS 待持久化"],
          ["ep_bar2_phy_addr probe + SYNC", "已写 0x9c0000000"],
          ["EP inbound ATU bar2+0x2000", "idx=3 cpu=0x4fa000000"],
          ["kernel #12 ATU 误判修复", "写入成功即 done · 无 10s 重试"],
          ["zboot.img → boot 分区", "已刷 #12 · 2026-08-21 21:19 KST"],
          ["PWM6 fan_ctrl → pwm-fan", "✅ hwmon0 手动调速 · 2026-08-26"],
          ["play_wav route guard", "✅ Headphone Switch 播中守护 · 2026-08-26"],
        ]}
        striped
      />

      <H2>⑲ R1 PWM6 风扇 — DTS 改造规格（VM 编 boot）</H2>
      <Callout tone="success" title="PWM 手动调速已通过（2026-08-26 · hwmon0）">
        <Code>pwm-fan</Code> 驱动已绑定 · <Code>hwmon0</Code> 名称 <Code>pwmfan</Code> ·
        <Code>fan_ctrl</Code> GPIO 已移除。本板<strong>无 pwm1_enable</strong>，直接写 <Code>pwm1</Code>：
        <Code>echo 200 &gt; /sys/class/hwmon/hwmon0/pwm1</Code> 回读 200 · adb 复验 64/200 均 OK。
        供应商：<Code>febd0020.pwm</Code>（DTS 标签 pwm6）。
      </Callout>
      <Table
        headers={["项", "路径 / 命令", "实测", "结果"]}
        rows={FAN_PWM_VERIFY.map((r) => [...r])}
        rowTone={["success", "success", "success", "success", "success", "success", "neutral", "neutral"]}
        striped
      />
      <Callout tone="warning" title="原根因（改 DTS 前 · 2026-08-26 上午）">
        物理接 <strong>PWM6</strong>，但 Ubuntu 镜像实际走 <Code>fan_ctrl</Code> GPIO（0/1），<strong>PWM6 disabled</strong>，
        <Code>pwm-fan</Code> 未绑定 → 空闲 ~29°C 仍 <Code>state=1</Code> 满速。
        目标：<strong>disable fan_ctrl · enable &amp;pwm6 · pwm-fan 温控</strong>，只烧 boot，保留 pcie-rkep / hugepages。
      </Callout>
      <Table
        headers={["组件", "DTS/驱动", "板端实测", "结论"]}
        rows={FAN_DTS_AUDIT.map((r) => [...r])}
        rowTone={["danger", "warning", "warning", "warning", "success", "neutral"]}
        striped
      />
      <Table
        headers={["步骤", "动作", "说明"]}
        rows={FAN_DTS_CHECKLIST.map((r) => [...r])}
        striped
      />
      <Table
        headers={["内核选项", "值", "说明"]}
        rows={FAN_DTS_KERNEL_CONFIG.map((r) => [...r])}
        striped
      />

      <CollapsibleSection title="⑲a DTS 补丁参考（复制到 *yyt*.dtsi）" trailing={<Text size="small">Wiki + 板端审计</Text>}>
        <Code>{`/* A. 禁用 GPIO 风扇 — 释放 PWM6 控制权 */
fan_ctrl: fan_ctrl {
    compatible = "lylx,xgpio";
    /* gpio = <...>;  保留原值 */
    def_val = <0>;
    status = "disabled";
};

/* B. pwm-fan 节点（/ { } 内，label 与 cooling-map 一致） */
fan: pwm-fan {
    compatible = "pwm-fan";
    #cooling-cells = <2>;
    pwms = <&pwm6 0 50000 0>;   /* 20kHz；若仍像满速可改 10000000=100Hz */
    cooling-levels = <0 50 100 150 200 255>;
    rockchip,temp-trips = <
        50000 1
        55000 2
        60000 3
        65000 4
        70000 5
    >;
    status = "okay";
};

/* C. 启用 PWM6 控制器 */
&pwm6 {
    pinctrl-0 = <&pwm6m0_pins>;
    pinctrl-names = "default";
    status = "okay";
};

/* D. soc-thermal 追加（勿删原有 cpufreq map） */
/* trips { } 内： */
soc_fan_trip1: soc-fan-trip1 {
    temperature = <50000>;
    hysteresis = <2000>;
    type = "active";
};
/* cooling-maps { } 内： */
map_fan0 {
    trip = <&soc_fan_trip1>;
    cooling-device = <&fan 1 5>;
};`}</Code>
        <Text size="small" tone="secondary">
          静音向可选：cooling-levels = &lt;0 30 80 120 180 220&gt; · temp-trips 起转 45°C。
          勿动 CONFIG_PCIE_DW_ROCKCHIP_EP · 勿删 bootargs hugepages=160。
        </Text>
      </CollapsibleSection>

      <CollapsibleSection title="⑲b 刷机后验收（adb shell）" trailing={<Text size="small">通过判据</Text>}>
        <CommandBlock title="板端" items={TEST_COMMANDS.fan} />
        <Divider />
        <CommandBlock title="VM 编译" items={TEST_COMMANDS.fanVm} />
        <Text size="small" tone="secondary">
          通过：hwmon0=pwmfan · pwm-fan driver 绑定 · echo pwm1 可回读。
          本板无 pwm1_enable；勿用 fan_ctrl（已移除）。
          自动温控走 pwm-fan 内 rockchip,temp-trips；thermal cooling_device 未挂 pwm-fan 属可选优化。
        </Text>
      </CollapsibleSection>

      <H2>⑳ J368 喇叭 — PulseAudio 路由冲突修复（2026-08-26）</H2>
      <Callout tone="success" title="speaker_test 用户确认可听 · play_wav route guard 已部署">
        软件链路正常（<Code>aplay</Code> 成功 · peak~26000），但 PulseAudio 在
        <Code>pasuspender -- aplay -D plughw:0,0</Code> 期间把 ES8388
        <strong>Headphone Switch（numid=28）</strong> 关掉 → J368 无声。
        <Code>play_wav.sh</Code> 增加 <Code>spk_route_guard</Code>：播放中每 30ms 检查并恢复路由，播后再执行一次
        <Code>speaker_setup.sh</Code>。
      </Callout>
      <Table
        headers={["项", "路径 / 命令", "实测", "结果"]}
        rows={SPK_ROUTE_VERIFY.map((r) => [...r])}
        rowTone={["info", "warning", "neutral", "success", "success", "success", "success", "success"]}
        striped
      />
      <Callout tone="warning" title="为何 8/22 冻结验收后仍会复发">
        v2 配置走 <Code>PLAYBACK_ROUTE=headphone</Code>（J368 SH1.25 L/R），该路径会被桌面 PulseAudio 抢回混音器；
        早期板载 <Code>Speaker Switch</Code> 路径在同样流程下<strong>不会被关</strong>，故不易复现。
        桌面自动登录后 PA 长期占 <Code>/dev/snd/controlC0</Code>，问题更易触发——属软件争用，非喇叭硬件故障。
      </Callout>
      <CollapsibleSection title="⑳a 板端验收（adb shell）" trailing={<Text size="small">通过判据</Text>}>
        <Code>{`# 标准喇叭测试（滴声 + TTS）
bash /userdata/voice/scripts/speaker_test.sh

# 路由终态（headphone 路径）
amixer -c 0 cget numid=28 | grep values   # Headphone Switch → on
amixer -c 0 cget numid=29 | grep values   # Speaker Switch   → off
amixer -c 0 cget numid=35 | grep values   # Mono Mux stereo  → 0

# 若仍无声：确认 J368 GND+L+R · 勿插 3.5mm TRS · 喇叭供电
# 备选路由：PLAYBACK_ROUTE=onboard bash …/speaker_test.sh`}</Code>
        <Text size="small" tone="secondary">
          修复文件：<Code>/userdata/voice/scripts/play_wav.sh</Code>（PC：
          youyeetoo3588s/voice/scripts/play_wav.sh）。beep · tts · asr 回放均经此脚本。
        </Text>
      </CollapsibleSection>

      <Card>
        <CardHeader>pcie-rkep.c 关键路径</CardHeader>
        <CardBody>
          <Stack gap={8}>
            <Text size="small">1. probe / SYNC 写 ep_bar2_phy_addr</Text>
            <Text><Code>obj_info-&gt;ep_bar2_phy_addr = pci_resource_start(pdev, 2);</Code></Text>
            <Text size="small">2. EP inbound ATU（与 librknnsmi bar2+0x2000 一致）</Text>
            <Text><Code>BAR2 inbound ATU via bar2+0x2000 idx=3 cpu=0x4fa000000</Code></Text>
            <Text size="small">3. #12：bar2 写入成功 → bar2_atu_done，跳过读回 0xffffffff 校验</Text>
          </Stack>
        </CardBody>
      </Card>

      <CollapsibleSection title="⑰ P4 RTSP 看图（adb shell）" trailing={<Text size="small">VLM+TTS · 192.168.2.x</Text>}>
        <Stack gap={12}>
          <Table
            headers={["分工", "芯片", "说明"]}
            rows={[
              ["RTSP 取帧", "RK3588S", "GStreamer+MPP · tcp h264 640×480"],
              ["VLM 短描述", "RM1828", "InternVL3.5-4B · Vision ~190ms"],
              ["TTS 播报", "RK3588 CPU", "p4_tts · voice_hw v2 · P4_TTS=1"],
              ["1828 预检", "—", "p4_check_1828 · >80MB 拒绝"],
              ["P5 目标", "按需", "热待机 daemon · chat↔see 免 reboot"],
            ]}
            striped
          />
          <CommandBlock title="板端测试命令" items={TEST_COMMANDS.p4} />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="⑯ 语音 I/O 测试（P3.5 · adb shell）" trailing={<Text size="small">3588 · 验收冻结</Text>}>
        <Stack gap={12}>
          <Table
            headers={["分工", "芯片", "栈 / 冻结值"]}
            rows={[
              ["麦克风采集 / 喇叭播放", "RK3588S", "ES8388 · main_board · gain=8"],
              ["ASR", "RK3588 CPU", "SenseVoice · prep_asr_wav · max 25x"],
              ["TTS", "RK3588 CPU", "VITS-Melo · normalize peak 26000 · ch=2"],
              ["LLM 对话", "RM1828", "InternVL llm-only · llm_ask.py · max_new=64"],
              ["冻结入口", "voice_hw_board.sh v2", "asr_tts.sh · voice_chat.sh"],
              ["暂缓", "换麦 / RNNoise", "FY-SP701 已到 · P3.6 独立验收"],
            ]}
            striped
          />
          <CommandBlock title="板端测试命令" items={TEST_COMMANDS.voice} />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="⑯c FY-SP701 USB 模组（P3.6 · adb shell）" trailing={<Text size="small">plughw:1,0 · --live 11 PASS</Text>}>
        <Stack gap={12}>
          <Table
            headers={["分工", "位置", "说明"]}
            rows={[
              ["麦克风+功放", "FY-SP701 V3 USB", "cafe:b20a · card1 · 2MIC+5W"],
              ["前端 DSP", "模组固件", "AEC/ANC/AGC/DNN · 仅 PCM 输出"],
              ["ASR", "R1 CPU", "Streaming Paraformer · 非模组文本 API"],
              ["验收", "phase_3_6_test.sh", "2026-08-28 · 11 PASS"],
              ["下一步", "Agent 集成", "vad+TTS 路由 · GUI 设置 Modal"],
            ]}
            striped
          />
          <CommandBlock title="板端测试命令" items={TEST_COMMANDS.p36} />
          <CommandBlock title="Windows 推送" items={TEST_COMMANDS.p36Win} />
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="⑯b 语音脚本推送（P3.5 · Windows adb）" trailing={<Text size="small">PC → 板端</Text>}>
        <CommandBlock title="" items={TEST_COMMANDS.voiceWin} />
      </CollapsibleSection>

      <H2>语音流水线（当前）</H2>
      <VoicePipelineGraph />

      <H2>视觉流水线（P4 已打通）</H2>
      <VisionPipelineGraph />

      <H2>实施路线</H2>
      <Row gap={8} wrap>
        {PHASES.map((p) => (
          <span key={p.id}>
            <Pill active={p.id === phaseId} onClick={() => setPhaseId(p.id)}>
              {p.name}
            </Pill>
          </span>
        ))}
      </Row>

      <Grid columns="1.2fr 1fr" gap={16}>
        <Card>
          <CardHeader trailing={<Pill size="sm" active>{phase.days}</Pill>}>
            {phase.name}
          </CardHeader>
          <CardBody>
            <Stack gap={12}>
              <Text>
                本关工作：{phase.work}。通过标准：{phase.gate}。
              </Text>
              <TodoList todos={TODOS[phase.id]} />
            </Stack>
          </CardBody>
        </Card>
        <Stack gap={12}>
          <H3>关卡门禁</H3>
          <Table
            headers={["关", "不通过就停"]}
            rows={PHASES.map((p) => [p.name.replace(/P\d\s/, ""), p.gate])}
            rowTone={PHASES.map((p) =>
              p.id === phaseId ? "info" : "neutral",
            )}
          />
        </Stack>
      </Grid>

      <CollapsibleSection title="编译环境 dev 待办">
        <TodoList todos={TODOS.dev} />
      </CollapsibleSection>

      <H2>1 秒预算（InternVL3.5-4B · 目标）</H2>
      <BarChart
        categories={["短描述 32 tok", "中答 80 tok", "长答 150 tok"]}
        series={[
          { name: "视觉编码", data: [177, 177, 177], tone: "info" },
          { name: "TTFT", data: [110, 110, 110], tone: "neutral" },
          { name: "文本生成", data: [364, 909, 1705], tone: "warning" },
        ]}
        stacked
        height={220}
        valueSuffix=" ms"
        yMax={2200}
        referenceLines={[{ value: 1000, label: "1s 预算", tone: "danger" }]}
      />
      <UsageBar
        total={1000}
        topLeftLabel="短描述打进 1s：约 651 / 1000 ms"
        topRightLabel="177 + 110 + 32×11.4 ms"
        segments={[
          { id: "vision", value: 177, color: "blue" },
          { id: "ttft", value: 110, color: "gray" },
          { id: "decode", value: 364, color: "orange" },
        ]}
      />

      <Text tone="tertiary" size="small">
        最后更新 2026-08-28 17:40 UTC+8 · P3.6 FY-SP701 --live 11 PASS · P5c GUI 设置待办 ·
        P0–P4 原型全通 · agent/ 代码库 · VM gp@192.168.100.196
      </Text>
    </Stack>
  );
}
