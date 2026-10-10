/* Content review: 2026-10-09. Historical board evidence: PROGRESS.md, August 2026. */
window.projectData = {
  repo: "https://github.com/xiaolaohu123wf/youyeetoo3588s_vlm",
  ref: "codex/project-overview",
  nodes: [
    {name:"采集与检测",tag:"ALSA / VAD",host:"RK3588S · 音频输入",text:"自动选择 FY-SP701 USB 阵列麦或 ES8388 板载音频。Silero VAD 检测语音边界，并保留开头预卷与尾部补帧。",note:"输入切分影响识别完整性；参数由音频 profile 和 agent.yaml 管理。",file:"agent/asr/vad_stream.py"},
    {name:"语音识别",tag:"Paraformer",host:"RK3588S · CPU",text:"Paraformer 接收音频分块并产生部分识别结果，在语句结束后输出最终文本。也可配置 SenseVoice 备用后端。",note:"当前 finalize 会重新处理整段音频，实时字幕与最终识别的路径有所区别。",file:"agent/asr/asr_engine.py"},
    {name:"对话编排",tag:"asyncio",host:"RK3588S · Python",text:"状态机协调识别、模型与播放，维护最近四轮历史，处理语音设置快捷指令、回复兜底和播放打断。",note:"十分钟无模型对话后清除历史；每次请求前清空模型 KV cache 并回放文本历史。",file:"agent/orchestrator/main.py"},
    {name:"模型推理",tag:"RKNN3 / LLM",host:"RK1828 · 加速推理",text:"C++ 常驻服务加载 InternVL3.5-4B 的 LLM 四件套，经 Unix socket 接收 JSON Lines 请求并返回 token 流。",note:"当前仅加载语言模型。专用 InternVL chat template 代码仍处于禁用状态。",file:"agent/daemon/llm_daemon.cpp"},
    {name:"清洗与合成",tag:"Matcha / VITS",host:"RK3588S · CPU",text:"完整回答生成后进行清洗、兜底与分句，使用 Matcha 或 VITS 合成。合成与播放由独立队列推进。",note:"模型 token 流式显示，但正常回答不会逐 token 立即转成语音。",file:"agent/tts/tts_queue.py"},
    {name:"播放与交互",tag:"ALSA / WebSocket",host:"RK3588S · 扬声器与网页",text:"播放语音并广播识别文本、模型 token 和状态。HDMI 与局域网共用控制面板，支持音量、音色、语速及调试。",note:"HTTP 8766 / WebSocket 8765。项目介绍页独立于板端实时控制面板。",file:"agent/ui/index.html"}
  ],
  modules: [
    {path:"agent/",label:"当前主线",title:"端侧语音智能体",text:"后续功能优化的主要入口。Python 编排语音链路，C++ 维持模型常驻，网页展示状态并修改设置。",files:[["agent/orchestrator/main.py","状态机与对话编排"],["agent/config/agent.yaml","模型、音频与接口配置"],["agent/ui/index.html","板端实时控制面板"],["agent/api/debug_audio.py","录音、回放与直通调试"]]},
    {path:"voice/",label:"音频基础",title:"语音原型与底层资源",text:"早期音频对话脚本、音频硬件配置、RKNN Session 示例与 sherpa-onnx 相关安装资源。部分音频脚本仍被主线复用。",files:[["voice/scripts/voice_hw_board.sh","ES8388 硬件参数"],["voice/scripts/fy_sp701_hw.sh","USB 阵列麦参数"],["voice/scripts/play_wav.sh","板载音频播放"],["voice/src/rknn3_session_test.cpp","Session 推理基线"]]},
    {path:"p4/",label:"视觉原型",title:"RTSP 看图链路",text:"取摄像头最新帧、中心裁剪到 448×448，然后调用独立 VLM demo 描述画面。还未统一到 agent，推理时需避免争用 RK1828。",files:[["p4/README.md","配置与原型使用方式"],["p4/scripts/p4_test.sh","单轮取帧与看图"],["p4/scripts/frame_prepare.py","图像预处理"],["p4/scripts/rtsp_daemon.sh","RTSP 取帧服务"]]},
    {path:"demo / models",label:"推理资源",title:"模型示例与本地权重",text:"InternVL 和 Qwen3-VL 的推理示例用于验证视觉语言能力。大型权重、SDK 与刷机工具不随 Git 源码发布，需要单独准备。",files:[["rknn_InternVLM_demo","InternVL 推理示例"],["rknn_Qwen3_VL_demo","Qwen3-VL 推理示例"],["agent/docs/TECH_PLAN.md","常驻模型与资源路径"],[".gitignore","权重与工具忽略规则"]]},
    {path:"scripts / services",label:"部署运行",title:"把源码送到板端",text:"Windows 使用 adb 推送，Linux 板端安装 systemd 服务，负责模型、编排、HDMI GUI、USB 共存和 WiFi AP 启动。",files:[["agent/scripts/push_local_deploy.ps1","完整本地部署"],["agent/scripts/install_autostart.sh","安装自启动服务"],["agent/systemd/r1-orchestrator.service","编排服务生命周期"],["agent/docs/BUILD_LINUX.md","daemon 编译说明"]]},
    {path:"docs / canvases",label:"文档路线",title:"说明、记录与项目网页",text:"根目录 README 提供总览，PROGRESS 保留历史验收数据，agent/docs 记录实施说明。此项目介绍页由纯静态文件发布到 GitHub Pages。",files:[["README.md","项目结构与部署总览"],["PROGRESS.md","阶段与历史测试记录"],["agent/docs/ARCHITECTURE.md","架构决策"],["docs/site/data.js","网页内容与进度数据"]]}
  ],
  stages: [
    {id:"P0",name:"硬件通电与连接",state:"done",status:"已完成",text:"已记录 PCIe 182a 识别与 adb 连接，建立主控和加速卡的调试通路。",evidence:"来源：PROGRESS.md · P0 总览",file:"PROGRESS.md"},
    {id:"P1",name:"软件栈与基础推理",state:"done",status:"已完成",text:"内核 #12、HugePage 160 与 RKNN3 1.0.5b10 软件栈已验证。Qwen3-0.6B 历史记录约 155 tok/s。",evidence:"历史板端记录；性能依赖模型与具体测试条件。",file:"PROGRESS.md"},
    {id:"P2",name:"静态图像理解",state:"done",status:"已完成",text:"InternVL3.5-4B 与 Qwen3-VL-4B 示例完成端到端验证。InternVL 单次视觉编码历史记录约 191 ms。",evidence:"来源：PROGRESS.md · 2026-08-21，示例图片测试。",file:"PROGRESS.md"},
    {id:"P3",name:"独立文本对话",state:"done",status:"已完成",text:"InternVL3.5-4B 的语言部分可以独立推理，不加载 vision。128 token 输出测试约 80 tok/s。",evidence:"来源：PROGRESS.md · 2026-08-21；不是当前版本的重新实测。",file:"PROGRESS.md"},
    {id:"P4",name:"RTSP 视觉感知",state:"open",status:"原型通过",text:"TCP 取帧、640×480 到 448×448 中心裁剪与画面描述已经冒烟通过。stock demo 每轮重载模型，历史整轮约 30 秒。",evidence:"1fps 是取帧目标，不是端到端 VLM 描述速度；统一常驻仍待实现。",file:"p4/README.md"},
    {id:"P5",name:"语音对话智能体",state:"open",status:"进行中",text:"常驻模型、流式识别、TTS 队列、历史对话、播放打断与 GUI 已实现。当前重点是统一 see()、chat template 与首响优化。",evidence:"来源：agent 源码 + PROGRESS.md。正常 TTS 等完整回答清洗后开始。",file:"agent/README.md"},
    {id:"P6",name:"部署与产品化",state:"open",status:"部分完成",text:"已提供 systemd 自启、HDMI GUI、FY-SP701 与 adb 共存、WiFi AP 以及音频调试能力。长期稳定性和完整回归待持续验证。",evidence:"来源：agent/systemd、agent/scripts 与 USB / WiFi 文档；功能存在不等于最新硬件验收。",file:"agent/docs/WIFI_AP_WEBUI.md"}
  ]
};
