@echo off
setlocal
cd /d "%~dp0backend"
if not exist .env copy .env.example .env
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
python scripts\init_db.py
start "eligibility-backend" cmd /k "call .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
cd /d "%~dp0frontend"
if not exist node_modules npm install
start "eligibility-frontend" cmd /k "npm run dev"
echo.
echo ??: http://127.0.0.1:8000/docs
echo ??: http://127.0.0.1:5173
endlocal
