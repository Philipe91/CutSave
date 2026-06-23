# -*- mode: python ; coding: utf-8 -*-
"""Spec do PrintNest (PyInstaller) - executavel unico Windows para PySide6.

Fonte unica de verdade da build: o build.bat apenas chama
``pyinstaller --noconfirm PrintNest.spec``. Para regenerar a build, ver build.bat.
"""
from pathlib import Path

# Empacota o icone como recurso (alem de defini-lo como icone do .exe), para que
# a janela/barra de tarefas mostrem o icone tambem em tempo de execucao.
_icon = "assets/printnest.ico"
_has_icon = Path(_icon).exists()
datas = [(_icon, "assets")] if _has_icon else []

# Toolkits/pesos que o app nao usa: evita inchar o executavel se algo os puxar.
excludes = [
    "tkinter",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "matplotlib",
    "IPython",
    "pytest",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
]

a = Analysis(
    ["printnest_main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PrintNest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[_icon] if _has_icon else None,
)
