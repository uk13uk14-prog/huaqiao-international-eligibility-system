@echo off
setlocal
cd /d "%~dp0"
if not exist .env copy .env.example .env
if not exist node_modules npm install
npm run dev
endlocal
