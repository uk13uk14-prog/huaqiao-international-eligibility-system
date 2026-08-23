@echo off
setlocal
cd /d "%~dp0backend"
if not exist .env copy .env.example .env
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
python scripts\init_db.py
start "saas-pro-backend" cmd /k "call .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8010"
cd /d "%~dp0frontend"
if not exist node_modules npm install
start "saas-pro-frontend" cmd /k "npm run dev"
echo SaaS Pro ??: http://127.0.0.1:5180
echo SaaS Pro ??: http://127.0.0.1:8010/docs
endlocal
