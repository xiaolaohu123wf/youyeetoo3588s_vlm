# Deploy adb+SP701 boot fix to R1 (wait for adb, push, install)
param(
    [string]$Root = "C:\Users\wwff\Documents\youyeetoo3588s",
    [int]$WaitSec = 180
)

$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding $false

function Fix-Lf($src, $dst) {
    $t = [IO.File]::ReadAllText($src).Replace("`r`n", "`n")
    [IO.File]::WriteAllText($dst, $t, $utf8)
}

Write-Host "[deploy-usb-fix] waiting for adb (up to ${WaitSec}s)..."
Write-Host "[deploy-usb-fix] if stuck: unplug FY-SP701 -> systemctl restart usbdevice -> replug SP701 to HOST port"
$deadline = (Get-Date).AddSeconds($WaitSec)
while ((Get-Date) -lt $deadline) {
    $out = adb devices 2>&1 | Out-String
    if ($out -match '(?m)^[0-9a-fA-F]+\s+device$') {
        Write-Host "[deploy-usb-fix] adb connected"
        break
    }
    Start-Sleep -Seconds 4
}
$check = (adb devices 2>&1 | Out-String)
if ($check -notmatch 'device\s*$' -and $check -notmatch '\sdevice') {
    throw "adb not found - unplug SP701 from HOST, restart usbdevice on board, plug PC to DEBUG port"
}

$tmp = Join-Path $env:TEMP "r1-usb-fix"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

$files = @(
    @("$Root\agent\scripts\retry_usbdevice.sh", "$tmp\retry_usbdevice.sh", "/userdata/agent/scripts/retry_usbdevice.sh"),
    @("$Root\agent\scripts\recover_adb_after_sp701.sh", "$tmp\recover_adb_after_sp701.sh", "/userdata/agent/scripts/recover_adb_after_sp701.sh"),
    @("$Root\agent\scripts\patch_alsactl_profile.sh", "$tmp\patch_alsactl_profile.sh", "/userdata/agent/scripts/patch_alsactl_profile.sh"),
    @("$Root\agent\scripts\test_sp701_adb.sh", "$tmp\test_sp701_adb.sh", "/userdata/agent/scripts/test_sp701_adb.sh"),
    @("$Root\agent\scripts\install_usb_adb_mic_boot.sh", "$tmp\install_usb_adb_mic_boot.sh", "/userdata/agent/scripts/install_usb_adb_mic_boot.sh"),
    @("$Root\agent\systemd\r1-usbdevice-retry.service", "$tmp\r1-usbdevice-retry.service", "/userdata/agent/systemd/r1-usbdevice-retry.service"),
    @("$Root\agent\systemd\r1-adb-sp701-recover.service", "$tmp\r1-adb-sp701-recover.service", "/userdata/agent/systemd/r1-adb-sp701-recover.service"),
    @("$Root\agent\systemd\99-r1-sp701-adb-recover.rules", "$tmp\99-r1-sp701-adb-recover.rules", "/userdata/agent/systemd/99-r1-sp701-adb-recover.rules")
)

foreach ($f in $files) {
    Fix-Lf $f[0] $f[1]
    adb push $f[1] $f[2] | Out-Null
    Write-Host "[deploy-usb-fix] pushed $($f[2])"
}

adb shell "chmod +x /userdata/agent/scripts/retry_usbdevice.sh /userdata/agent/scripts/recover_adb_after_sp701.sh /userdata/agent/scripts/patch_alsactl_profile.sh /userdata/agent/scripts/test_sp701_adb.sh /userdata/agent/scripts/install_usb_adb_mic_boot.sh; sudo bash /userdata/agent/scripts/install_usb_adb_mic_boot.sh"
Write-Host ""
Write-Host "[deploy-usb-fix] done. Cold boot test: both cables plugged, wait ~30s, then: adb devices"
