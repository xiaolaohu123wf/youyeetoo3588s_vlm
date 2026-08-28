# Full local deploy from youyeetoo3588s repo (board needs adb, no network required)
param(
    [string]$Root = "C:\Users\wwff\Documents\youyeetoo3588s"
)

$ErrorActionPreference = "Stop"

function Test-Has($rel) { Test-Path (Join-Path $Root $rel) }

Write-Host "[local-deploy] root=$Root"
adb shell "df -h /userdata; mkdir -p /userdata/agent /userdata/voice /userdata/models"

& powershell -File "$Root\agent\scripts\push_agent.ps1"
& powershell -File "$Root\voice\scripts\push_voice.ps1"

# Config: pick ASR/TTS based on local folders
$cfgSrc = Join-Path $Root "agent\config\agent.yaml"
$cfgTmp = Join-Path $env:TEMP "agent.yaml"
$cfg = Get-Content $cfgSrc -Raw -Encoding UTF8
if (-not (Test-Has "voice\sherpa-onnx-streaming-paraformer-bilingual-zh-en\encoder.int8.onnx")) {
    Write-Host "[local-deploy] paraformer missing -> sense_voice ASR (partial on)"
    $cfg = $cfg -replace '(?ms)^asr:\r?\n.*?(?=^tts:)', @"
asr:
  backend: sense_voice
  model_dir: /userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17
  sherpa_bin: /userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline
  sherpa_lib: /userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib
  language: zh
  num_threads: 2
  partial_interval_sec: 0.8
  partial_min_sec: 0.6
  partial_enabled: true
  max_partials_per_utterance: 5

"@
}
if (-not (Test-Has "voice\matcha-icefall-zh-baker\model-steps-3.onnx")) {
    Write-Host "[local-deploy] matcha missing -> default_voice melo"
    $cfg = $cfg -replace 'default_voice: baker', 'default_voice: melo'
}
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($cfgTmp, $cfg.Replace("`r`n", "`n"), $utf8NoBom)
adb push $cfgTmp /userdata/agent/config/agent.yaml | Out-Null

& powershell -File "$Root\agent\scripts\push_models.ps1" -Root $Root

Write-Host "[local-deploy] install systemd + GUI"
adb shell "sudo bash /userdata/agent/scripts/install_autostart.sh"

Write-Host "[local-deploy] open GUI (HDMI session)"
adb shell "sudo -u youyeetoo bash /userdata/agent/scripts/open_agent_gui.sh" 2>&1 | Select-Object -Last 5

Write-Host ""
Write-Host "[local-deploy] status:"
adb shell "systemctl is-active r1-llm-daemon r1-orchestrator r1-agent-gui 2>/dev/null; ls /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.rknn 2>/dev/null; tail -3 /userdata/agent/logs/orchestrator.log 2>/dev/null"
