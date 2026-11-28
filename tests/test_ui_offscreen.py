"""Offscreen UI integration tests for MainWindow:
- Preset application updates UI and synchronizes settings
- Stale result detection disables Print/Save
- Defect blocking banner disables Print/Save until explicit confirmation
"""

import os
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.pipeline import PipelineResult
from app.settings_manager import SettingsManager
from app.ui.main_window import MainWindow

# Ensure Qt runs offscreen in headless test runners
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp, tmp_path, monkeypatch):
    SettingsManager.reset()
    fake_appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    sm = SettingsManager()
    win = MainWindow(sm)
    win.show()
    yield win
    win.close()
    SettingsManager.reset()


def test_preset_application(main_window):
    """Applying a preset should update photo size, paper size, and copies with signals blocked."""
    # Find preset for "Indian Passport (8 copies)" or similar
    presets = main_window.settings.load_presets()
    target_preset = next((p for p in presets if "Indian Passport" in p["name"]), presets[0])

    # Find index in combo
    idx = -1
    for i in range(main_window.preset_combo.count()):
        data = main_window.preset_combo.itemData(i)
        if data and data.get("name") == target_preset["name"]:
            idx = i
            break

    assert idx != -1
    main_window.preset_combo.setCurrentIndex(idx)

    # UI controls must reflect the preset
    assert main_window.photo_size_combo.currentData() == target_preset["photo_size"]
    assert main_window.paper_size_combo.currentData() == target_preset["paper_size"]
    assert main_window.copies_spin.value() == target_preset["copies"]


def test_stale_result_disables_print_save(main_window):
    """When current UI values differ from the result's snapshot, Print/Save must be disabled."""
    # Simulate an existing processed result
    dummy_photo = Image.new("RGB", (413, 531), (200, 200, 200))
    dummy_sheet = Image.new("RGB", (1200, 1800), (255, 255, 255))

    snapshot = main_window._get_current_ui_settings()
    res = PipelineResult(
        final_photo=dummy_photo,
        sheets=[dummy_sheet],
        num_sheets=1,
        copies=snapshot["copies"],
        photo_size_mm=(35.0, 45.0),
        settings_snapshot=snapshot.copy(),
    )

    main_window.latest_result = res
    main_window._update_action_buttons_state()

    # Initially matching settings: buttons enabled
    assert main_window.print_btn.isEnabled() is True
    assert main_window.save_btn.isEnabled() is True

    # Shopkeeper changes copies from 8 to 12 without re-processing
    main_window.copies_spin.setValue(12)
    main_window._update_action_buttons_state()

    # P0: Result is now stale versus UI, so buttons MUST be disabled to avoid printing wrong count!
    assert main_window._is_result_stale() is True
    assert main_window.print_btn.isEnabled() is False
    assert main_window.save_btn.isEnabled() is False


def test_blocking_defect_banner_and_confirmation(main_window):
    """If a result has blocking defects (e.g. no face detected), Print/Save are disabled

    until the shopkeeper explicitly checks the confirmation checkbox.
    """
    dummy_photo = Image.new("RGB", (413, 531), (200, 200, 200))
    dummy_sheet = Image.new("RGB", (1200, 1800), (255, 255, 255))

    snapshot = main_window._get_current_ui_settings()
    res = PipelineResult(
        final_photo=dummy_photo,
        sheets=[dummy_sheet],
        num_sheets=1,
        copies=snapshot["copies"],
        photo_size_mm=(35.0, 45.0),
        blocking_issues=["No human face detected in photo. Generic center crop applied."],
        settings_snapshot=snapshot.copy(),
    )

    main_window.latest_result = res
    main_window._evaluate_safety_banners(res)
    main_window._update_action_buttons_state()

    # Red banner must be shown
    assert not main_window.banner_frame.isHidden()
    assert "DEFECT DETECTED" in main_window.banner_label.text()

    # Print and Save MUST be disabled!
    assert main_window.print_btn.isEnabled() is False
    assert main_window.save_btn.isEnabled() is False

    # Check the explicit confirmation checkbox
    main_window.confirm_defect_cb.setChecked(True)
    main_window._update_action_buttons_state()

    # Now enabled after shopkeeper explicit confirmation
    assert main_window.print_btn.isEnabled() is True
    assert main_window.save_btn.isEnabled() is True

    # Uncheck confirmation again
    main_window.confirm_defect_cb.setChecked(False)
    main_window._update_action_buttons_state()
    assert main_window.print_btn.isEnabled() is False
    assert main_window.save_btn.isEnabled() is False


def test_ui_alignments_and_titles(main_window):
    """Verify GroupBox titles avoid mnemonic underlines and controls maintain uniform geometry."""
    from PySide6.QtWidgets import QGroupBox, QScrollArea

    # Check titles have literal && to avoid keyboard accelerator underscores
    groups = {g.title(): g for g in main_window.findChildren(QGroupBox)}
    assert any("Photo Size && Print Copies" in t for t in groups.keys()), f"Titles: {list(groups.keys())}"
    assert any("Lighting && Touch-up" in t for t in groups.keys()), f"Titles: {list(groups.keys())}"

    # Verify input controls in Size group have matching x and width
    main_window.resize(1150, 800)
    QApplication.processEvents()

    ps_geo = main_window.photo_size_combo.geometry()
    paper_geo = main_window.paper_size_combo.geometry()
    copies_geo = main_window.copies_spin.geometry()

    assert ps_geo.x() == paper_geo.x() == copies_geo.x(), "Inputs must share the same left column x-coordinate"
    assert ps_geo.width() == paper_geo.width() == copies_geo.width(), "Inputs must share identical widths"

    # Verify color preview is placed to the right of bg_combo
    bg_geo = main_window.bg_combo.geometry()
    prev_geo = main_window.color_preview.geometry()
    assert prev_geo.x() >= bg_geo.x() + bg_geo.width(), "Color preview swatch must be on the right of combo"

    # Verify scroll widget does not exceed scroll area width (no horizontal overflow)
    scrolls = main_window.findChildren(QScrollArea)
    assert len(scrolls) > 0
    scroll = scrolls[0]
    w = scroll.widget()
    assert w.width() <= scroll.width(), f"Scroll content {w.width()} must fit inside scroll area {scroll.width()}"

