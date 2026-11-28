# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for Passport Photo App.

Packages the complete application into a standalone Windows executable.
- Disables UPX (upx=False) to prevent DLL corruption and false antivirus alerts.
- Bundles isnet-general-use.onnx and blaze_face_short_range.tflite.
- Uses collect_all for rembg, onnxruntime, mediapipe, pymatting.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Determine project root from SPECPATH (defined by PyInstaller)
try:
    project_dir = Path(SPECPATH).resolve().parent
except NameError:
    project_dir = Path(".").resolve()

# Base data files
datas = [
    (str(project_dir / "config"), "config"),
    (str(project_dir / "assets"), "assets"),
    (str(project_dir / "app" / "ui" / "styles.qss"), "app/ui"),
]

binaries = []

# Bundle required models explicitly
isnet_path = project_dir / "models" / "isnet-general-use.onnx"
if isnet_path.exists():
    datas.append((str(isnet_path), "models"))

blaze_path = project_dir / "models" / "blaze_face_short_range.tflite"
if blaze_path.exists():
    datas.append((str(blaze_path), "models"))

# Optional u2net fallback model if user has it
u2net_path = project_dir / "models" / "u2net.onnx"
if u2net_path.exists():
    datas.append((str(u2net_path), "models"))

# Base hidden imports
hidden_imports = [
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
]

# collect_all for packages with native binaries, ONNX runtimes, and models
for pkg in ["rembg", "onnxruntime", "mediapipe", "pymatting"]:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas.extend(pkg_datas)
        binaries.extend(pkg_binaries)
        hidden_imports.extend(pkg_hidden)
    except Exception as exc:
        print(f"Warning: collect_all({pkg}) failed: {exc}")

a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir)],
    binaries=binaries,
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
    upx=False,  # P2: Disable UPX compression to avoid AV false-positives and DLL breakage
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
    upx=False,  # P2: Disable UPX
    upx_exclude=[],
    name="PassportPhotoApp",
)
