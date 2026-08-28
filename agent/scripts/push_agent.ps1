# Push agent scripts to board (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$Root\agent\scripts\llm_client.py")) {
    $Root = "C:\Users\wwff\Documents\youyeetoo3588s"
}
$Board = "/userdata/agent"

Write-Host "[push] $Root\agent -> $Board"

adb shell "mkdir -p $Board/bin $Board/scripts $Board/config $Board/logs $Board/run $Board/asr $Board/orchestrator $Board/ui $Board/systemd"

function Push-Lf($Local, $Remote) {
    $content = [System.IO.File]::ReadAllText($Local).Replace("`r`n", "`n")
    $tmp = [IO.Path]::GetTempFileName()
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, $content, $utf8)
    adb push $tmp $Remote | Out-Null
    Remove-Item $tmp -Force
}

function Push-PyTree($LocalDir, $RemoteDir) {
    if (-not (Test-Path $LocalDir)) { return }
    Get-ChildItem $LocalDir -Filter "*.py" -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring($LocalDir.Length).TrimStart('\','/')
        $remote = "$RemoteDir/$($rel -replace '\\','/')"
        adb shell "mkdir -p $(Split-Path $remote -Parent)" 2>$null | Out-Null
        Push-Lf $_.FullName $remote
    }
}

Push-PyTree "$Root\agent\asr" "$Board/asr"
Push-PyTree "$Root\agent\orchestrator" "$Board/orchestrator"
Push-PyTree "$Root\agent\llm" "$Board/llm"
Push-PyTree "$Root\agent\tts" "$Board/tts"
Push-PyTree "$Root\agent\api" "$Board/api"

Get-ChildItem "$Root\agent\scripts" -Filter "*.py" | ForEach-Object {
    Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
}
Get-ChildItem "$Root\agent\scripts" -Filter "*.sh" | ForEach-Object {
    Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
}
Push-Lf "$Root\agent\config\agent.yaml" "$Board/config/agent.yaml"

Get-ChildItem "$Root\agent\ui" -File | ForEach-Object {
    Push-Lf $_.FullName "$Board/ui/$($_.Name)"
}
Get-ChildItem "$Root\agent\systemd" -Filter "*.service" | ForEach-Object {
    Push-Lf $_.FullName "$Board/systemd/$($_.Name)"
}
Get-ChildItem "$Root\agent\scripts" -Filter "*.desktop" | ForEach-Object {
    Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
}

adb shell "chmod +x $Board/scripts/*.sh 2>/dev/null; chmod +x $Board/bin/* 2>/dev/null; ls -la $Board/scripts/"

if (Test-Path "$Root\agent\bin\llm_daemon") {
    adb push "$Root\agent\bin\llm_daemon" "$Board/bin/llm_daemon"
    adb shell "chmod +x $Board/bin/llm_daemon"
    Write-Host "[push] llm_daemon binary pushed"
} else {
    Write-Host "[push] no agent/bin/llm_daemon — compile on Linux VM first (agent/docs/BUILD_LINUX.md)"
}

Write-Host "[push] done. Tests:"
Write-Host "  Phase A: adb shell bash $Board/scripts/phase_a_test.sh"
Write-Host "  Phase B: adb shell bash $Board/scripts/phase_b_test.sh"
Write-Host "  Phase C: adb shell bash $Board/scripts/phase_c_test.sh"
Write-Host "  Phase D: adb shell bash $Board/scripts/phase_d_test.sh"
Write-Host "  Phase E: adb shell bash $Board/scripts/phase_e_test.sh"
Write-Host "  Phase 3.6: adb shell bash $Board/scripts/phase_3_6_test.sh"
Write-Host "  WS probe: adb shell python3 $Board/scripts/ws_probe.py"
Write-Host "  Autostart: adb shell sudo bash $Board/scripts/install_autostart.sh"
