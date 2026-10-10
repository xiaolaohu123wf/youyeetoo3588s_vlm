# Post-flash full deploy: agent + voice + models + systemd + GUI
# Usage:
#   powershell -File agent/scripts/deploy_after_flash.ps1
#   powershell -File agent/scripts/deploy_after_flash.ps1 -InternVLPath "D:\models\InternVL3_5-4B"
#   powershell -File agent/scripts/deploy_after_flash.ps1 -SkipModels
param(
    [string]$InternVLPath = "",
    [switch]$SkipModels,
    [switch]$SkipBootstrap,
    [int]$AdbWaitSec = 300
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$Root\agent\scripts\push_agent.ps1")) {
    $Root = "C:\Users\wwff\Documents\youyeetoo3588s"
}

function Wait-Adb {
    param([int]$TimeoutSec)
    Write-Host "[deploy] waiting for adb device (up to ${TimeoutSec}s)..."
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $out = adb devices 2>$null
        if ($out -match "(?m)^[0-9a-fA-F]+\s+device$") {
            Write-Host "[deploy] adb connected"
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "adb device not found — enable USB debugging or connect network adb"
}

function Push-TreeIfExists($Local, $Remote) {
    if (-not (Test-Path $Local)) {
        Write-Host "[deploy] skip missing $Local"
        return $false
    }
    Write-Host "[deploy] push $Local -> $Remote (may take a while)"
    adb shell "mkdir -p $Remote"
    adb push "$Local/." "$Remote/"
    return $true
}

Wait-Adb -TimeoutSec $AdbWaitSec

Write-Host "[deploy] ensure /userdata mount"
adb shell "df -h /userdata; mkdir -p /userdata/agent /userdata/voice /userdata/models"

Write-Host "[deploy] push agent code"
& powershell -File "$Root\agent\scripts\push_agent.ps1"

Write-Host "[deploy] push voice scripts"
& powershell -File "$Root\voice\scripts\push_voice.ps1"

if (-not $SkipModels) {
    $SherpaLocal = "$Root\voice\sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu"
    Push-TreeIfExists $SherpaLocal "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu" | Out-Null

    $MeloLocal = "$Root\voice\vits-melo-tts-zh_en"
    Push-TreeIfExists $MeloLocal "/userdata/voice/vits-melo-tts-zh_en" | Out-Null

    $WnjLocal = "$Root\voice\vits-zh-hf-fanchen-wnj"
    Push-TreeIfExists $WnjLocal "/userdata/voice/vits-zh-hf-fanchen-wnj" | Out-Null

    if ($InternVLPath -and (Test-Path $InternVLPath)) {
        Push-TreeIfExists $InternVLPath "/userdata/models/InternVL3_5-4B" | Out-Null
    } else {
        Write-Host "[deploy] InternVL not pushed — pass -InternVLPath or adb push manually"
    }
} else {
    Write-Host "[deploy] -SkipModels: board will wget small models in bootstrap"
}

adb shell "chmod +x /userdata/agent/scripts/*.sh /userdata/voice/scripts/*.sh 2>/dev/null; sed -i 's/\r$//' /userdata/agent/scripts/*.sh /userdata/voice/scripts/*.sh 2>/dev/null || true"

if (-not $SkipBootstrap) {
    Write-Host "[deploy] run board bootstrap (download ASR/TTS if needed, install systemd)"
    adb shell "sudo bash /userdata/agent/scripts/bootstrap_board.sh"
}

Write-Host ""
Write-Host "[deploy] done. Quick checks:"
Write-Host "  adb shell systemctl status r1-llm-daemon r1-orchestrator r1-agent-gui --no-pager"
Write-Host "  adb shell bash /userdata/agent/scripts/phase_e_test.sh"
Write-Host "  adb shell bash /userdata/agent/scripts/repair_gui.sh"
