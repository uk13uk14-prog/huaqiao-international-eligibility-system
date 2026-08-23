$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Path "huaqiao-app-h5.zip") { Remove-Item "huaqiao-app-h5.zip" }
Compress-Archive -Path "dist\*" -DestinationPath "huaqiao-app-h5.zip"
Write-Host "H5 包已生成: huaqiao-app-h5.zip"
