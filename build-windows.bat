@echo off
REM ============================================================
REM  Huaqiao Eligibility - Windows Standalone Build Script
REM  Run this on a Windows machine with Python 3.10+ and Node.js 18+
REM ============================================================

setlocal enabledelayedexpansion

REM Get the script directory (project root)
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo ============================================================
echo  华侨生资格评估系统 - Windows 安装包构建
echo ============================================================
echo.
echo Project directory: %SCRIPT_DIR%
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    exit /b 1
)

REM Step 1: Install backend dependencies
echo [1/6] Installing backend dependencies...
cd /d "%SCRIPT_DIR%\backend"
pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies
    exit /b 1
)
echo       Done.

REM Step 2: Build backend with PyInstaller
echo [2/6] Building backend executable...
pyinstaller huaqiao-backend.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] Failed to build backend
    exit /b 1
)
echo       Done. Output: backend\dist\huaqiao-backend\

REM Step 3: Install frontend dependencies
echo [3/6] Installing frontend dependencies...
cd /d "%SCRIPT_DIR%\frontend"
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies
    exit /b 1
)
echo       Done.

REM Step 4: Build Vue frontend
echo [4/6] Building Vue frontend...
call npm run build
if errorlevel 1 (
    echo [ERROR] Failed to build frontend
    exit /b 1
)
echo       Done.

REM Step 5: Build Electron installer
echo [5/6] Building Electron installer...
call npx electron-builder --win --x64
if errorlevel 1 (
    echo [ERROR] Failed to build Electron installer
    exit /b 1
)
echo       Done.

REM Step 6: Report
echo [6/6] Build complete!
echo.
echo ============================================================
echo  Output files:
echo ============================================================
dir /b "%SCRIPT_DIR%\frontend\release\*.exe" 2>nul
echo.
echo  The installer is ready for distribution.
echo ============================================================

endlocal
