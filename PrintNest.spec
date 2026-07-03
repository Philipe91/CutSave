# -*- mode: python ; coding: utf-8 -*-
"""Spec do PrintNest (PyInstaller) - executavel unico Windows para PySide6.

Fonte unica de verdade da build: o build.bat apenas chama
``pyinstaller --noconfirm PrintNest.spec``. Para regenerar a build, ver build.bat.
"""
from pathlib import Path

# Empacota TODA a pasta assets como recurso (icone do exe + logo/simbolo +
# os SVGs dos botoes da barra). Sem isso, no executavel os botoes saem sem
# icone e o logo nao aparece, pois o codigo resolve os caminhos via _MEIPASS.
_icon = "assets/printnest.ico"
_has_icon = Path(_icon).exists()

# (arquivo_origem, pasta_destino_no_bundle) para cada arquivo dentro de assets/,
# preservando a subpasta (ex.: assets/icons/lock.svg -> assets/icons).
# Ignora scripts .py auxiliares (ex.: make_icon.py) que nao sao recursos.
datas = [
    (str(p), str(Path("assets") / p.relative_to("assets").parent))
    for p in Path("assets").rglob("*")
    if p.is_file() and p.suffix.lower() != ".py"
]

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
    # licenciamento: os modulos entram por importacao lazy (so no exe), garante
    # que o PyInstaller empacote a cryptography e as licenses do app.
    hiddenimports=[
        "cryptography",
        "app.licensing.manager",
        "app.presentation.licensing_dialog",
    ],
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
