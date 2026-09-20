$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Plugin = Join-Path $Root "plugin"
$Version = (Get-Content (Join-Path $Plugin "manifest.json") -Raw | ConvertFrom-Json).version
$BaseName = "FTGirl-DDL-FDM-v$Version"
$Out = Join-Path $Root "$BaseName.fda"
$Tmp = Join-Path $Root "$BaseName.zip"

Remove-Item $Out,$Tmp -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Plugin "*") -DestinationPath $Tmp -CompressionLevel Optimal
Move-Item $Tmp $Out
Write-Host "Built: $Out"
