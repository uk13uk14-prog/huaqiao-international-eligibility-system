#!/bin/bash
#
# Coze Deploy Adapter - Production Start Script
#
# This script:
# 1. Validates required environment variables
# 2. Installs backend dependencies
# 3. Installs frontend dependencies (npm ci)
# 4. Builds frontend
# 5. Runs Alembic migrations
# 6. Starts API server on port 9091
# 7. Starts SPA server on port 9090
#
# Usage: ./start.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# ==============================================================================
# STEP 1: Environment Variable Validation
# ==============================================================================

log_info "Validating required environment variables..."

REQUIRED_VARS=(
    "DATABASE_URL"
    "VAULT_FERNET_KEY"
    "ADMIN_TOKEN"
    "JWT_SECRET_KEY"
    "PRIVACY_HMAC_SECRET"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    log_error "Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

# Validate DATABASE_URL is PostgreSQL (not SQLite)
if [[ "$DATABASE_URL" == sqlite* ]]; then
    log_error "SQLite is not allowed in production!"
    log_error "DATABASE_URL must be PostgreSQL: postgresql://..."
    exit 1
fi

log_info "Environment variables validated."

# ==============================================================================
# STEP 2: Install Backend Dependencies
# ==============================================================================

log_info "Installing backend dependencies..."
cd "$BACKEND_DIR"
pip install -r requirements.txt --quiet
log_info "Backend dependencies installed."

# ==============================================================================
# STEP 3: Install Frontend Dependencies
# ==============================================================================

log_info "Installing frontend dependencies (npm ci)..."
cd "$FRONTEND_DIR"

if [ ! -f "package-lock.json" ]; then
    log_error "package-lock.json not found in frontend/"
    log_error "Cannot use npm ci without lockfile."
    exit 1
fi

npm ci
log_info "Frontend dependencies installed."

# ==============================================================================
# STEP 4: Build Frontend
# ==============================================================================

log_info "Building frontend..."
npm run build

if [ ! -d "dist" ]; then
    log_error "Frontend build failed: dist/ directory not found"
    exit 1
fi

log_info "Frontend built successfully."

# ==============================================================================
# STEP 5: Database Migration
# ==============================================================================

log_info "Running Alembic migrations..."
cd "$BACKEND_DIR"
alembic upgrade head
log_info "Database migrations completed."

# ==============================================================================
# STEP 6: Start API Server (port 9091)
# ==============================================================================

log_info "Starting API server on port 9091..."
cd "$BACKEND_DIR"
uvicorn app.main:app --host 0.0.0.0 --port 9091 --log-level info &
API_PID=$!
log_info "API server started (PID: $API_PID)"

# ==============================================================================
# STEP 7: Start SPA Server (port 9090)
# ==============================================================================

log_info "Starting SPA server on port 9090..."
cd "$PROJECT_ROOT"
python -m deploy_adapter.serve_spa --host 0.0.0.0 --port 9090 &
SPA_PID=$!
log_info "SPA server started (PID: $SPA_PID)"

# ==============================================================================
# STEP 8: Health Check and Wait
# ==============================================================================

log_info "Waiting for services to start..."
sleep 3

# Check if processes are still running
if ! kill -0 $API_PID 2>/dev/null; then
    log_error "API server (port 9091) failed to start"
    exit 1
fi

if ! kill -0 $SPA_PID 2>/dev/null; then
    log_error "SPA server (port 9090) failed to start"
    exit 1
fi

log_info "Both services started successfully."
log_info "  - SPA:  http://0.0.0.0:9090"
log_info "  - API:  http://0.0.0.0:9091"

# Handle shutdown signals
cleanup() {
    log_info "Shutting down services..."
    kill $API_PID $SPA_PID 2>/dev/null
    wait $API_PID $SPA_PID 2>/dev/null
    log_info "Services stopped."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for both processes
wait $API_PID $SPA_PID
