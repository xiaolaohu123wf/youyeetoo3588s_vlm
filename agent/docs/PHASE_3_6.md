# Phase 3.6 — FY-SP701 V3 USB 阵列麦 + 功放

> **硬件**：华芸科技 FY-SP701 V3 · USB 2.0 · 2MIC 线性阵列 · 16 kHz · 8Ω 5W 功放  
> **板端识别**：`lsusb` → `cafe:b20a Timesintelli USB Audio Device` · ALSA **card 1** · `plughw:1,0`  
> **与 P3.5 关系**：P3.5 冻结板载 ES8388（`plughw:0,0`）；P3.6 **独立**测 USB 模组，不改动冻结配置。

## 快速验收

```bash
# PC 推送脚本
bash voice/scripts/push_voice.sh
powershell -File agent/scripts/push_agent.ps1

# 板端（adb shell）
bash /userdata/agent/scripts/phase_3_6_test.sh          # 标准（含需说话步骤）
bash /userdata/agent/scripts/phase_3_6_test.sh --quick   # 跳过 ASR 失败判定
bash /userdata/agent/scripts/phase_3_6_test.sh --live    # 末尾跑 ASR→TTS 交互
```

## 单项脚本

| 脚本 | 作用 |
|------|------|
| `voice/scripts/fy_sp701_detect.sh` | 自动找 USB 声卡号 |
| `voice/scripts/fy_sp701_hw.sh` | 环境变量（16 kHz · 2ch · 播放增益） |
| `voice/scripts/fy_sp701_play.sh` | 经模块功放播放 WAV |
| `voice/scripts/fy_sp701_record.sh` | USB 采集 |
| `voice/scripts/fy_sp701_mic_diag.sh` | 录音 → 分析 → 回放 → ASR |
| `voice/scripts/fy_sp701_asr_tts.sh` | **P3.6 标准验收** · 说一句话 → TTS 复读 |

## 验收项（phase_3_6_test.sh）

1. USB / ALSA 枚举（lsusb · aplay/arecord -l）
2. 模块喇叭播放 880/660 Hz 提示音
3. 双麦立体声 3s 采集 + `analyze_stereo_wav.py`
4. 16 kHz 采样率确认
5. AEC 粗测（安静 vs 播放 tone 时采集）
6. SenseVoice ASR（上一步录音）
7. TTS 经模块功放播放
8. 可选 `fy_sp701_asr_tts.sh` 闭环（`--live`）

## 安装注意（来自手册）

- 双 MIC 进声孔独立、声路短（<1.5 mm）、无空腔
- 喇叭与 MIC 不同腔体或密封，避免结构传声
- MIC 远离喇叭震动；硅胶套减震

## 接入 Agent（已集成）

`agent.yaml` 默认 `audio.default_profile: auto` — USB FY-SP701 插入时自动用 `plughw:1,0` + `fy_sp701_play.sh`，否则板载 ES8388。

```bash
# 强制 USB 模组
AGENT_AUDIO_PROFILE=fy_sp701 bash /userdata/agent/scripts/start_orchestrator.sh

# 强制板载
AGENT_AUDIO_PROFILE=board bash /userdata/agent/scripts/start_orchestrator.sh
```

日志应出现：`[audio] profile=fy_sp701 ... capture=plughw:1,0` · `[vad] listening on plughw:1,0`

持久化：`/userdata/agent/run/user_settings.json`（GUI 设置 Modal 后续写入）

## 故障排查

| 现象 | 检查 |
|------|------|
| 未找到 USB 卡 | `lsusb`、`dmesg \| tail`、换 USB 口 |
| 双麦一路 dead | 线序 / 拾音头安装 / `analyze_stereo_wav.py` |
| ASR 空 | 靠近模组说话；peak>1500；跑 `fy_sp701_mic_diag.sh` |
| 播放无声 | 外接 8Ω 喇叭是否接模块功放输出；`amixer -c 1` |
| 全双工回声大 | 手册 AEC 为硬件侧；实机对话测 `fy_sp701_asr_tts.sh` |
