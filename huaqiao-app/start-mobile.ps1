$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
if (!(Test-Path "node_modules")) { npm install }
npm run dev
