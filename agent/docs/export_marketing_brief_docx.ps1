# Generate Word .docx for marketing brief (requires Microsoft Word). Reads BRIEF.md UTF-8.
$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$md = Join-Path $dir "HARDWARE_WHITEPAPER_MARKETING_BRIEF.md"
$out = Join-Path $dir "HARDWARE_WHITEPAPER_MARKETING_BRIEF.docx"
$lines = Get-Content -LiteralPath $md -Encoding UTF8
$title = ($lines | Where-Object { $_ -match '^#\s+' } | Select-Object -First 1) -replace '^#\s+', ''
$paras = New-Object System.Collections.Generic.List[string]
$buf = New-Object System.Text.StringBuilder
foreach ($line in $lines) {
  if ($line -match '^\s*#' -or $line -match '^\s*---' -or $line -match '字数说明') { continue }
  if ($line.Trim() -eq '') {
    if ($buf.Length -gt 0) {
      [void]$paras.Add(($buf.ToString() -replace '\*\*', '').Trim())
      $buf.Clear() | Out-Null
    }
    continue
  }
  [void]$buf.Append($line.Trim())
  [void]$buf.Append(' ')
}
if ($buf.Length -gt 0) {
  [void]$paras.Add(($buf.ToString() -replace '\*\*', '').Trim())
}
$fontEast = 'MSYH'
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $doc = $word.Documents.Add()
  $range = $doc.Range(0, 0)
  $range.Text = $title + [char]13 + [char]13
  $range.Font.Size = 16
  $range.Font.Bold = $true
  $range.Font.NameFarEast = $fontEast
  foreach ($p in $paras) {
    $r = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
    $r.Text = $p + [char]13 + [char]13
    $r.Font.Size = 12
    $r.Font.Bold = $false
    $r.Font.NameFarEast = $fontEast
    $r.ParagraphFormat.LineSpacingRule = 1
    $r.ParagraphFormat.LineSpacing = 18
  }
  if (Test-Path $out) { Remove-Item -Force $out }
  $fmt = 16
  $doc.SaveAs([ref]$out, [ref]$fmt) | Out-Null
  $doc.Close()
  $word.Quit()
  [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($word)
  Write-Host "OK $out"
} catch {
  Write-Error $_
  exit 1
}
