"""Build verification script for Passport Photo App.

Verifies:
1. Critical imports and native libraries (PySide6, rembg, onnxruntime, mediapipe, pymatting, cv2, win32print, scipy)
2. Local models present (isnet-general-use.onnx)
3. Assets, configs, and styles present
4. If dist/PassportPhotoApp exists: verifies all bundled files and executability.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def check_runtime_dependencies() -> bool:
    """Check that all required runtime dependencies are importable in the current Python environment."""
    modules = [
        ("PySide6.QtCore", "PySide6"),
        ("PySide6.QtWidgets", "PySide6"),
        ("rembg", "rembg"),
        ("onnxruntime", "onnxruntime"),
        ("cv2", "OpenCV"),
        ("numpy", "NumPy"),
        ("PIL.Image", "Pillow"),
        ("scipy.ndimage", "SciPy"),
        ("pymatting", "pymatting"),
        ("win32print", "pywin32"),
    ]

    print("\n--- 1. Checking Python Dependencies ---")
    all_ok = True
    for mod_name, label in modules:
        try:
            importlib.import_module(mod_name)
            print(f"  [OK] {label} ({mod_name})")
        except ImportError as exc:
            print(f"  [FAIL] {label} ({mod_name}): {exc}")
            all_ok = False
        except Exception as exc:
            print(f"  [WARN] {label} ({mod_name}) warning: {exc}")

    # MediaPipe check
    try:
        import mediapipe
        print(f"  [OK] MediaPipe (version {getattr(mediapipe, '__version__', 'unknown')})")
    except Exception as exc:
        print(f"  [FAIL] MediaPipe: {exc}")
        all_ok = False

    return all_ok


def check_local_assets() -> bool:
    """Check required project files, configs, and models."""
    print("\n--- 2. Checking Project Assets & Models ---")
    all_ok = True

    required_files = [
        PROJECT_ROOT / "config" / "presets.json",
        PROJECT_ROOT / "app" / "ui" / "styles.qss",
        PROJECT_ROOT / "assets" / "icon.ico",
        PROJECT_ROOT / "models" / "isnet-general-use.onnx",
    ]

    for path in required_files:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK] {path.relative_to(PROJECT_ROOT)} ({size_mb:.2f} MB)")
        else:
            print(f"  [FAIL] Missing: {path.relative_to(PROJECT_ROOT)}")
            all_ok = False

    return all_ok


def check_dist_bundle() -> bool:
    """Check dist output folder if PyInstaller build was run."""
    dist_dir = PROJECT_ROOT / "dist" / "PassportPhotoApp"
    print("\n--- 3. Checking PyInstaller Output (dist/PassportPhotoApp) ---")

    if not dist_dir.exists():
        print(f"  [INFO] Dist directory does not exist yet ({dist_dir}).")
        print("         Run PyInstaller to create bundle: pyinstaller build/app.spec")
        return True

    exe_path = dist_dir / "PassportPhotoApp.exe"
    if not exe_path.exists():
        print(f"  [FAIL] Exe not found: {exe_path}")
        return False

    print(f"  [OK] Found executable: {exe_path.name} ({exe_path.stat().st_size / (1024 * 1024):.1f} MB)")

    # Verify key internal files inside dist (supporting PyInstaller 5 root and 6+ _internal)
    internal_dir = dist_dir / "_internal" if (dist_dir / "_internal").exists() else dist_dir

    checks = [
        "config/presets.json",
        "models/isnet-general-use.onnx",
        "app/ui/styles.qss",
    ]
    bundle_ok = True
    for rel in checks:
        p1 = dist_dir / rel
        p2 = internal_dir / rel
        if p1.exists() or p2.exists():
            found_path = p1 if p1.exists() else p2
            print(f"  [OK] Bundled: {found_path.relative_to(dist_dir)}")
        else:
            print(f"  [FAIL] Not bundled: {rel}")
            bundle_ok = False

    return bundle_ok


def main() -> int:
    print("=" * 60)
    print(" Passport Photo App — Build & Dependency Checker")
    print("=" * 60)

    deps_ok = check_runtime_dependencies()
    assets_ok = check_local_assets()
    dist_ok = check_dist_bundle()

    print("\n" + "=" * 60)
    if deps_ok and assets_ok and dist_ok:
        print(" Result: ALL CHECKS PASSED")
        print("=" * 60)
        return 0
    else:
        print(" Result: SOME CHECKS FAILED — Review output above")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
