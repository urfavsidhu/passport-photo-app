"""Capture offscreen screenshots of Passport Photo App in Light and Dark themes."""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.settings_manager import SettingsManager
from app.ui.adjust_crop_dialog import AdjustCropDialog
from app.ui.main_window import MainWindow
from app.ui.setup_wizard import SetupWizard
from app.ui.theme import apply_theme

ARTIFACT_DIR = Path(r"C:\Users\sidha\.gemini\antigravity\brain\0d3c470d-3db1-4f9f-be67-fbee38e30eae")
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_all() -> None:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    sm = SettingsManager()

    # 1. Light Mode Screenshots
    apply_theme(app, is_dark=False)

    # MainWindow (Light)
    win_light = MainWindow(sm)
    win_light.resize(1200, 800)
    win_light.show()
    app.processEvents()
    pix_win_light = win_light.grab()
    path_win_light = SCREENSHOT_DIR / "mainwindow_light.png"
    pix_win_light.save(str(path_win_light))
    print(f"Captured: {path_win_light}")
    win_light.close()

    # SetupWizard (Light)
    wiz_light = SetupWizard(sm)
    wiz_light.resize(750, 600)
    wiz_light.show()
    app.processEvents()
    pix_wiz_light = wiz_light.grab()
    path_wiz_light = SCREENSHOT_DIR / "setup_wizard_light.png"
    pix_wiz_light.save(str(path_wiz_light))
    print(f"Captured: {path_wiz_light}")
    wiz_light.close()

    # 2. Dark Mode Screenshots
    apply_theme(app, is_dark=True)

    # MainWindow (Dark)
    win_dark = MainWindow(sm)
    win_dark.resize(1200, 800)
    win_dark.show()
    app.processEvents()
    pix_win_dark = win_dark.grab()
    path_win_dark = SCREENSHOT_DIR / "mainwindow_dark.png"
    pix_win_dark.save(str(path_win_dark))
    print(f"Captured: {path_win_dark}")
    win_dark.close()

    # SetupWizard (Dark)
    wiz_dark = SetupWizard(sm)
    wiz_dark.resize(750, 600)
    wiz_dark.show()
    app.processEvents()
    pix_wiz_dark = wiz_dark.grab()
    path_wiz_dark = SCREENSHOT_DIR / "setup_wizard_dark.png"
    pix_wiz_dark.save(str(path_wiz_dark))
    print(f"Captured: {path_wiz_dark}")
    wiz_dark.close()

    # 3. MainWindow with Defect Blocking Banner (Light)
    apply_theme(app, is_dark=False)
    win_banner = MainWindow(sm)
    win_banner.resize(1200, 800)
    win_banner.show()

    # Simulate loaded defect result
    from PIL import Image
    from app.core.pipeline import PipelineResult
    dummy_photo = Image.new("RGB", (413, 531), (210, 210, 210))
    dummy_sheet = Image.new("RGB", (1200, 1800), (255, 255, 255))
    defect_res = PipelineResult(
        final_photo=dummy_photo,
        sheets=[dummy_sheet],
        num_sheets=1,
        copies=8,
        photo_size_mm=(35.0, 45.0),
        blocking_issues=[
            "No human face detected in photo. A generic center crop was applied.",
            "Cutout alpha coverage (3.1%) is below safety threshold (5.0%).",
        ],
        settings_snapshot=win_banner._get_current_ui_settings(),
    )
    win_banner.latest_result = defect_res
    win_banner._evaluate_safety_banners(defect_res)
    win_banner._update_action_buttons_state()
    app.processEvents()

    pix_banner = win_banner.grab()
    path_banner = SCREENSHOT_DIR / "mainwindow_defect_banner.png"
    pix_banner.save(str(path_banner))
    print(f"Captured: {path_banner}")
    win_banner.close()


if __name__ == "__main__":
    capture_all()
