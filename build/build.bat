@echo off
setlocal enabledelayedexpansion

echo =========================================================
echo    Passport Photo App — Automated Build & Package
echo =========================================================

cd /d "%~dp0\.."

REM 1. Activate Virtual Environment or use local python
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    set "PYINSTALLER_EXE=venv\Scripts\pyinstaller.exe"
) else (
    set "PYTHON_EXE=python"
    set "PYINSTALLER_EXE=pyinstaller"
)

echo [1/3] Verifying offline models...
if not exist "models\isnet-general-use.onnx" (
    if not exist "models\u2net.onnx" (
        echo [WARNING] No ONNX model found in models\ folder.
        echo Downloading models now...
        "%PYTHON_EXE%" tools\download_models.py
    )
)
if not exist "models\blaze_face_short_range.tflite" (
    echo [WARNING] MediaPipe face detector not found in models\ folder.
    echo Downloading models now...
    "%PYTHON_EXE%" tools\download_models.py
)

echo [2/3] Building executable with PyInstaller...
"%PYINSTALLER_EXE%" --clean --noconfirm build\app.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    exit /b 1
)
echo [OK] PyInstaller build complete. Output in dist\PassportPhotoApp\

echo [3/3] Compiling Inno Setup Windows Installer...
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "!ISCC_PATH!" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist "!ISCC_PATH!" (
    set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)

if exist "!ISCC_PATH!" (
    echo Compiling installer with Inno Setup...
    "!ISCC_PATH!" "build\installer.iss"
    if errorlevel 1 (
        echo [ERROR] Inno Setup compilation failed!
        exit /b 1
    )
    echo =========================================================
    echo [SUCCESS] Windows Installer created at:
    echo dist\installer\PassportPhotoSetup.exe
    echo =========================================================
) else (
    echo [NOTE] Inno Setup compiler (ISCC.exe) not found on this system.
    echo Standalone application folder is ready at:
    echo %cd%\dist\PassportPhotoApp\PassportPhotoApp.exe
    echo To build Setup.exe, install Inno Setup 6 and re-run this script.
)

endlocal
exit /b 0
