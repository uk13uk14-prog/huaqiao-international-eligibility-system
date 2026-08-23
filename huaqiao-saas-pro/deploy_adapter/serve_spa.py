"""
Coze Deploy Adapter - SPA Static File Server

Serves Vue SPA from huaqiao-saas-pro/frontend/dist on port 9090.
Handles SPA fallback: all non-file routes return index.html.

This module:
- Does NOT import business FastAPI app
- Does NOT access database
- Does NOT copy API routes
- Does NOT modify frontend or backend code
"""

import argparse
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Resolve dist directory relative to this file
ADAPTER_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ADAPTER_DIR.parent / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"


def create_spa_app() -> FastAPI:
    """Create FastAPI app for serving Vue SPA."""
    app = FastAPI(
        title="SPA Static Server",
        version="1.0.0",
        docs_url=None,  # Disable docs for SPA server
        redoc_url=None,
        openapi_url=None,
    )

    if not DIST_DIR.exists():
        raise RuntimeError(
            f"Frontend dist directory not found: {DIST_DIR}\n"
            "Run 'npm run build' in frontend/ first."
        )

    assets_dir = DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "spa-server"}

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        """SPA fallback: return index.html for all routes."""
        index_file = DIST_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(
            content="<html><body><h1>SPA not built</h1><p>Run npm run build first</p></body></html>",
            status_code=503,
        )

    return app


def main():
    parser = argparse.ArgumentParser(description="Serve Vue SPA on port 9090")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=9090, help="Port to bind")
    args = parser.parse_args()

    import uvicorn

    app = create_spa_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
