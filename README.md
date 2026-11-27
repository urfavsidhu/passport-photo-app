# Passport Photo App (पासपोर्ट फोटो ऐप)

Desktop application designed for Indian CSC (Common Service Centre) and Digital Seva Kendra operators. Automatically turns raw camera portraits or uploaded files into ready-to-print passport photo sheets in 1 click.

---

## 🌟 Key Features

1. **100% Offline AI Background Removal**: Uses local ONNX model (`isnet-general-use` / `u2net`) via `rembg`. No internet connection needed at runtime.
2. **Smart Face Detection & Centering**: Automatically detects the subject's face using MediaPipe (with OpenCV Haar cascade fallback), crops to exact passport dimensions, and maintains correct head-to-photo height ratio (~75%).
3. **One-Click Instant Processing**: Select or capture a photo, and the app instantly performs background replacement, lighting optimization, cropping, and grid arrangement.
4. **Fast Touch-up Sliders**: Non-destructive sliders for Brightness, Contrast, Color Warmth, and Shadow Lift. Uses cached cutouts so adjustments update in real time without re-running AI models.
5. **Multi-Copy Sheet Layout**: Arranges 4, 8, 12, or 20+ copies on 4x6, 5x7, or A4 photo paper. Automatically rotates sheet for best fit and adds corner cut marks.
6. **100% Physical Size Printing**: Integrates with Windows `win32print` and `win32ui` to print at exact physical millimeters without distortion or "fit-to-page" scaling. Also supports multi-page PDF and PNG export.

---

## 🚀 Quick Setup & Installation

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.10+ (Recommended: Python 3.11)

### 1. Create and Activate Virtual Environment
```powershell
# In the project directory
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Download Offline AI Models (One-time step)
Run the automated downloader script to download the model into the `models/` directory:
```powershell
python tools/download_models.py
```

---

## 💻 Running the Application

### Launch GUI
```powershell
python main.py
```

### CLI Batch / Test Mode
You can test the entire processing pipeline from the command line:
```powershell
python -m app.core.pipeline data/input/sample.jpg --photo-size 35x45 --paper-size 4x6 --copies 8 --background white
```
Output files will be saved in `data/output/`.

---

## 🧪 Running Unit Tests
Unit tests verify mm-to-pixel math, sheet layout capacity, DPI metadata, and settings recovery:
```powershell
pytest -v
```

---

## 📦 Building the Standalone Executable & Installer

### 1. Build Standalone Folder (.exe)
```powershell
pyinstaller build\app.spec
```
The output executable will be placed in `dist\PassportPhotoApp\PassportPhotoApp.exe`.

### 2. Build Windows Installer (Setup.exe)
If you have [Inno Setup 6](https://jrsoftware.org/isdl.php) installed:
```cmd
build\build.bat
```
This produces `dist\installer\PassportPhotoSetup.exe`, an offline installer that can be deployed onto any Windows computer with **no Python installed**.

---

## 📂 Project Architecture

```
passport-photo-app/
├── main.py                     # Entry point & crash protection
├── requirements.txt            # Pinned dependencies
├── config/
│   ├── presets.json            # Common Indian ID/Passport presets
│   └── settings.json           # Template configuration schema
├── app/
│   ├── settings_manager.py     # Settings singleton & lookup tables
│   ├── core/
│   │   ├── background.py       # rembg AI model & alpha cleaning
│   │   ├── face_crop.py        # MediaPipe / Haar cascade face crop
│   │   ├── enhance.py          # Subject-only lighting adjustments
│   │   ├── layout.py           # Sheet grid packing & cut marks (pure Pillow)
│   │   └── pipeline.py         # Processing pipeline & cache
│   ├── camera/
│   │   └── capture.py          # Windows webcam capture (cv2.CAP_DSHOW)
│   ├── printing/
│   │   └── printer.py          # Physical-size Windows printing (pywin32)
│   └── ui/
│       ├── main_window.py      # Main desktop GUI (PySide6)
│       ├── setup_wizard.py     # First-run & settings wizard
│       ├── preview_panel.py    # Before/After & Sheet preview
│       └── styles.qss          # Modern light high-contrast theme
├── assets/
│   └── icon.ico                # Multi-resolution application icon
├── models/                     # Offline ONNX model files
├── tools/
│   └── download_models.py      # Offline model download utility
├── tests/
│   ├── test_layout.py          # Math & layout unit tests
│   └── test_settings.py        # Settings unit tests
└── build/
    ├── app.spec                # PyInstaller packaging spec
    ├── installer.iss           # Inno Setup script
    └── build.bat               # One-click build script
```
