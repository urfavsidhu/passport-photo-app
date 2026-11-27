"""Unit tests for SettingsManager and helper functions."""

import json
from pathlib import Path
import pytest

from app.settings_manager import (
    SettingsManager,
    DEFAULT_SETTINGS,
    photo_size_mm,
    paper_size_mm,
    background_hex,
)


@pytest.fixture(autouse=True)
def reset_singleton(tmp_path, monkeypatch):
    """Ensure clean SettingsManager state for each test using isolated temp path."""
    SettingsManager.reset()
    fake_appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    yield
    SettingsManager.reset()


def test_helper_photo_size_mm():
    assert photo_size_mm("35x45") == (35.0, 45.0)
    assert photo_size_mm("51x51") == (51.0, 51.0)
    assert photo_size_mm("20x25") == (20.0, 25.0)


def test_helper_paper_size_mm():
    assert paper_size_mm("4x6") == (101.6, 152.4)
    assert paper_size_mm("A4") == (210.0, 297.0)


def test_helper_background_hex():
    assert background_hex("white") == "#FFFFFF"
    assert background_hex("light_blue") == "#D6EAF8"
    assert background_hex("#123456") == "#123456"


def test_settings_load_save():
    sm = SettingsManager()
    assert sm.get("copies") == 8

    sm.set("copies", 12)
    assert sm.get("copies") == 12

    # Verify on disk
    with open(sm.path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["copies"] == 12


def test_settings_corrupted_file_recovery(tmp_path, monkeypatch):
    """If settings file is corrupted, it should load defaults and back up corrupted file."""
    fake_appdata = tmp_path / "AppData" / "Roaming"
    settings_dir = fake_appdata / "PassportPhotoApp"
    settings_dir.mkdir(parents=True, exist_ok=True)
    corrupted_file = settings_dir / "settings.json"
    corrupted_file.write_text("{ this is NOT valid JSON !!!", encoding="utf-8")

    sm = SettingsManager()
    # Defaults should be preserved
    assert sm.get("photo_size") == "35x45"
    assert sm.get("copies") == 8

    # Corrupted backup should exist
    backup = settings_dir / "settings.json.bak"
    assert backup.exists()
