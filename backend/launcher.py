"""
Huaqiao Eligibility Backend Launcher
Entry point for PyInstaller packaging.
Starts the FastAPI server with SQLite for standalone desktop mode.
"""

import os
import sys
import signal
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('huaqiao-backend')


def get_data_dir() -> Path:
    """Get the data directory for standalone mode."""
    if sys.platform == 'win32':
        # Windows: %APPDATA%\HuaqiaoEligibility
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = Path(appdata) / 'HuaqiaoEligibility'
    elif sys.platform == 'darwin':
        # macOS: ~/Library/Application Support/HuaqiaoEligibility
        data_dir = Path.home() / 'Library' / 'Application Support' / 'HuaqiaoEligibility'
    else:
        # Linux: ~/.local/share/huaqiao-eligibility
        data_dir = Path.home() / '.local' / 'share' / 'huaqiao-eligibility'
    
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_resource_dir() -> Path:
    """Get the resource directory (where bundled files are)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent


def setup_environment():
    """Setup environment variables for standalone mode."""
    data_dir = get_data_dir()
    
    # Create subdirectories
    (data_dir / 'data').mkdir(exist_ok=True)
    (data_dir / 'logs').mkdir(exist_ok=True)
    
    # Set database URL to SQLite in data directory
    db_path = data_dir / 'data' / 'eligibility.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    
    # Set environment to production (standalone mode)
    os.environ['ENV'] = 'production'
    
    # Set CORS to allow Electron file:// and localhost
    os.environ['CORS_ORIGINS'] = 'file://,http://localhost:9090,http://127.0.0.1:9090'
    
    # Generate a random admin token if not set
    if not os.environ.get('ADMIN_TOKEN'):
        import secrets
        os.environ['ADMIN_TOKEN'] = secrets.token_urlsafe(32)
    
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Database: {db_path}")
    
    return data_dir


def init_database():
    """Initialize the database with Alembic migrations."""
    from app.database import engine, Base
    from app import models  # noqa: F401 - Import models.py to register all models
    
    # Create tables directly (simpler than Alembic for standalone)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def run_server():
    """Start the FastAPI server."""
    import uvicorn
    from app.main import app
    
    # Run on 127.0.0.1 only (security requirement)
    host = '127.0.0.1'
    port = int(os.environ.get('BACKEND_PORT', '9090'))
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level='info',
        access_log=True,
    )


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Huaqiao Eligibility Backend - Standalone Mode")
    logger.info("=" * 50)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if sys.platform != 'win32':
        signal.signal(signal.SIGHUP, signal_handler)
    
    try:
        # Setup environment
        data_dir = setup_environment()
        
        # Initialize database
        init_database()
        
        # Run server
        run_server()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
