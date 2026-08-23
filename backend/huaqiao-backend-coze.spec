# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Huaqiao Eligibility Backend - Coze Desktop Release
Build command: pyinstaller huaqiao-backend-coze.spec
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all slowapi files
slowapi_datas, slowapi_binaries, slowapi_hiddenimports = collect_all('slowapi')

# Get the backend directory
backend_dir = os.path.dirname(os.path.abspath('__file__'))

a = Analysis(
    ['launcher.py'],
    pathex=[backend_dir],
    binaries=slowapi_binaries,
    datas=slowapi_datas + [
        # Include alembic migrations
        ('alembic', 'alembic'),
        ('alembic.ini', '.'),
        # Include any static files if needed
        ('static', 'static'),
    ],
    hiddenimports=[
        # FastAPI and dependencies
        'fastapi',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.responses',
        'starlette.routing',
        # SQLAlchemy
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.postgresql',
        'sqlalchemy.dialects.postgresql.psycopg',
        # Database drivers
        'sqlite3',
        'psycopg',
        'psycopg2',
        # Pydantic
        'pydantic',
        'pydantic_settings',
        # Cryptography (R4.3)
        'cryptography',
        'cryptography.fernet',
        # JWT
        'jose',
        'passlib',
        'passlib.hash',
        'passlib.hash.bcrypt',
        # Alembic
        'alembic',
        'alembic.config',
        'alembic.command',
        'alembic.script',
        'alembic.runtime.migration',
        # HTTP client
        'httpx',
        # Rate limiting
        'slowapi',
        'slowapi.errors',
        'slowapi.extension',
        'slowapi.middleware',
        'slowapi.util',
        'slowapi.wrappers',
        # Email
        'aiosmtplib',
        'email.message',
        # Utils
        'pytz',
        'dateutil',
        'multipart',
        'python_multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='huaqiao-backend-coze',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='huaqiao-backend-coze',
)
