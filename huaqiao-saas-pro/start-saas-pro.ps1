$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path "backend\.env")) { Copy-Item "backend\.env.example" "backend\.env" }
Set-Location backend
if (!(Test-Path ".venv")) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\init_db.py
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; . .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8010"
Set-Location ..\frontend
if (!(Test-Path "node_modules")) { npm install }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; npm run dev"
Write-Host "SaaS Pro 前端: http://127.0.0.1:5180"
Write-Host "SaaS Pro 后端: http://127.0.0.1:8010/docs"
