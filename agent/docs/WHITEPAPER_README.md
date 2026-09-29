# 小揽白皮书文档索引

| 文档 | 受众 | 文件 |
|------|------|------|
| **对外宣传白皮书** | 客户、展厅、投标宣讲 | [`HARDWARE_WHITEPAPER_MARKETING.pdf`](HARDWARE_WHITEPAPER_MARKETING.pdf)（首选） · [`.md`](HARDWARE_WHITEPAPER_MARKETING.md) · [`.html`](HARDWARE_WHITEPAPER_MARKETING.html) |
| **千字简介** | 直接粘贴 Word / 方案书摘要 | [`.doc`](HARDWARE_WHITEPAPER_MARKETING_BRIEF.doc)（Word 双击打开后可另存 `.docx`） · [`.md`](HARDWARE_WHITEPAPER_MARKETING_BRIEF.md) |
| **内部技术白皮书** | 研发、集成、验收（含型号与接口） | [`HARDWARE_TECHNICAL_WHITEPAPER.md`](HARDWARE_TECHNICAL_WHITEPAPER.md) · **勿对外发放** |

## 重新导出 PDF

在仓库根目录执行（需本机 Microsoft Edge）：

```powershell
$html = "agent\docs\HARDWARE_WHITEPAPER_MARKETING.html"
$pdf  = "agent\docs\HARDWARE_WHITEPAPER_MARKETING.pdf"
$uri  = ([Uri]$html).AbsoluteUri
& "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe" `
  --headless --disable-gpu --no-pdf-header-footer `
  --print-to-pdf="$((Resolve-Path $pdf).Path)" $uri
```

替换封面 Logo：编辑 HTML 中 `.logo-slot`，可改为 `<img src="..." alt="Logo" style="max-height:24mm">` 后重新导出。
