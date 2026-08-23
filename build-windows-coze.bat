@echo off
REM ============================================================
REM  Huaqiao Eligibility - Coze Desktop Release Build Script
REM  Independent build for GX10 distribution
REM  Product: HuaqiaoEligibility-Coze-v1.0.0.exe
REM ============================================================

setlocal enabledelayedexpansion

echo ============================================================
echo  华侨生资格评估系统 - Coze Desktop Release
echo  Independent Build for GX10
echo ============================================================
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
cd ..\backend
pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies
    exit /b 1
)
echo       Done.

REM Step 2: Build backend with PyInstaller
echo [2/6] Building backend executable...
pyinstaller huaqiao-backend-coze.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] Failed to build backend
    exit /b 1
)
echo       Done. Output: backend\dist\huaqiao-backend-coze\

REM Step 3: Install frontend dependencies
echo [3/6] Installing frontend dependencies...
cd ..\frontend
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

REM Step 5: Build Electron installer (Coze version)
echo [5/6] Building Coze Electron installer...
call npx electron-builder --win --x64 --config electron-builder.coze.json
if errorlevel 1 (
    echo [ERROR] Failed to build Electron installer
    exit /b 1
)
echo       Done.

REM Step 6: Report
echo [6/6] Build complete!
echo.
echo ============================================================
echo  Coze Desktop Release Output:
echo ============================================================
dir /b release\*Coze*.exe 2>nul
echo.
echo  Expected: HuaqiaoEligibility-Coze-v1.0.0.exe
echo  Ready for GX10 upload.
echo ============================================================

cd ..
endlocal
