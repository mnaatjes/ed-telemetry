# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for standalone Linux ed-telemetry executable."""

a = Analysis(
    ["../../src/ed_telemetry/bootstrap/container.py"],
    pathex=["../../src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ed-telemetry",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
