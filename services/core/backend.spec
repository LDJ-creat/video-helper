# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Video Helper Backend (FastAPI + Uvicorn)

Build command (run from services/core/):
    pyinstaller backend.spec --clean

Output: dist/backend/  (directory mode for faster startup)
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# The actual entry point
entry_script = 'main.py'

a = Analysis(
    [entry_script],
    pathex=['.', 'src'],
    binaries=[],
    datas=[
        # Include alembic migration files
        ('alembic', 'alembic'),
        ('alembic.ini', '.'),
        # faster-whisper ships runtime assets (e.g. silero_vad_v6.onnx)
        *collect_data_files('faster_whisper', includes=['assets/*']),
        # Source code is handled by binary analysis, no need to copy plain text folders
    ],
    hiddenimports=[
        # FastAPI / Starlette internals often missed by PyInstaller
        'anyio',
        'anyio.from_thread',
        'anyio._backends._asyncio',
        'starlette.middleware.cors',
        'starlette.routing',
        'starlette.responses',
        'starlette.requests',
        'starlette.background',
        # Uvicorn
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # SQLAlchemy dialects
        'sqlalchemy.dialects.sqlite',
        # Alembic
        'alembic.config',
        'alembic.runtime.migration',
        'alembic.runtime.environment',
        # Email validator (used by FastAPI[standard])
        'email_validator',
        # Multipart
        'multipart',
        'python_multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test dependencies
        'pytest',
        'pytest_asyncio',
        '_pytest',
        # Heavy ML libs that are loaded lazily (whisper loads them at runtime)
        # Keep these if whisper is bundled, remove if whisper runs externally
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    # Keep pure-Python modules on disk so faster_whisper.utils.__file__ resolves
    # to a real directory that also contains collected data files (assets/*.onnx).
    noarchive=True,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can break some native extensions
    console=True,  # Keep console=True so logs are visible; set False for silent
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='backend',
)
