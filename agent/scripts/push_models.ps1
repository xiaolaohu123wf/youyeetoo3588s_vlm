# Push voice/LLM models from local repo to board (no network on board)
param(
    [string]$Root = "C:\Users\wwff\Documents\youyeetoo3588s"
)

$ErrorActionPreference = "Stop"
adb shell "mkdir -p /userdata/voice /userdata/models"

function Push-Dir($Local, $Remote) {
    if (-not (Test-Path $Local)) {
        Write-Host "[models] skip missing $Local"
        return $false
    }
    Write-Host "[models] push $Local -> $Remote"
    adb shell "mkdir -p $Remote"
    adb push "$Local/." "$Remote/"
    return $true
}

function Push-File($Local, $Remote) {
    if (-not (Test-Path $Local)) {
        Write-Host "[models] skip missing $Local"
        return $false
    }
    Write-Host "[models] push $Local -> $Remote"
    adb push $Local $Remote
    return $true
}

Push-File "$Root\voice\silero_vad.onnx" "/userdata/voice/silero_vad.onnx" | Out-Null
Push-Dir "$Root\voice\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17" "/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17" | Out-Null
Push-Dir "$Root\voice\sherpa-onnx-streaming-paraformer-bilingual-zh-en" "/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en" | Out-Null
Push-Dir "$Root\voice\matcha-icefall-zh-baker" "/userdata/voice/matcha-icefall-zh-baker" | Out-Null
Push-File "$Root\voice\vocos-22khz-univ.onnx" "/userdata/voice/vocos-22khz-univ.onnx" | Out-Null
Push-Dir "$Root\InternVL3_5-4B" "/userdata/models/InternVL3_5-4B" | Out-Null

adb shell "chmod +x /userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/* 2>/dev/null; true"
Write-Host "[models] done"
