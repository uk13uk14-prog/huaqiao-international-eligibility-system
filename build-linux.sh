#!/bin/bash
# ============================================================
#  Huaqiao Eligibility - Linux Build Script (for testing)
# ============================================================

set -e

echo "============================================================"
echo "  华侨生资格评估系统 - Linux Build"
echo "============================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Install backend dependencies
echo "[1/5] Installing backend dependencies..."
cd backend
pip3 install -r requirements.txt pyinstaller --quiet
echo "       Done."

# Step 2: Build backend
echo "[2/5] Building backend executable..."
pyinstaller huaqiao-backend.spec --clean --noconfirm
echo "       Done. Output: backend/dist/huaqiao-backend/"

# Step 3: Install frontend dependencies
echo "[3/5] Installing frontend dependencies..."
cd ../frontend
npm install --silent
echo "       Done."

# Step 4: Build Vue frontend
echo "[4/5] Building Vue frontend..."
npm run build
echo "       Done."

# Step 5: Build Electron app
echo "[5/5] Building Electron app..."
npx electron-builder --linux
echo "       Done."

echo ""
echo "============================================================"
echo "  Build complete!"
echo "============================================================"
echo "  Output: frontend/release/"
ls -la release/*.AppImage 2>/dev/null || echo "  (No AppImage found)"
echo "============================================================"
