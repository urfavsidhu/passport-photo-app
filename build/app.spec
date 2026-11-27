# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for Passport Photo App.

Packages the complete application into a standalone Windows executable
including local models, configs, styles, and assets.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Determine project root from SPECPATH (defined by PyInstaller)
try:
    project_dir = Path(SPECPATH).resolve().parent
except NameError:
    project_dir = Path(".").resolve()

# Collect required data files
datas = [
    (str(project_dir / "config"), "config"),
    (str(project_dir / "models"), "models"),
    (str(project_dir / "assets"), "assets"),
    (str(project_dir / "app" / "ui" / "styles.qss"), "app/ui"),
]

# Collect hidden imports for libraries that dynamically load components
hidden_imports = [
    "rembg",
    "onnxruntime",
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
    "PIL.ImageEnhance",
    "PIL.ImageFilter",
    "PIL.ImageDraw",
    "PIL.ImageWin",
    "win32print",
    "win32ui",
    "win32con",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "scipy",
    "scipy.ndimage",
    "pymatting",
]

# Collect mediapipe if present
try:
    hidden_imports.extend(collect_submodules("mediapipe"))
    datas.extend(collect_data_files("mediapipe"))
except Exception:
    pass

# Collect rembg data
try:
    datas.extend(collect_data_files("rembg"))
except Exception:
    pass

a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
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
    name="PassportPhotoApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed application (no CMD popup)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PassportPhotoApp",
)
