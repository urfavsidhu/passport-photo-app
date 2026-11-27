"""Settings manager for Passport Photo App.

Provides SettingsManager singleton, resource_path(), user_data_dir(),
and helpers photo_size_mm(), paper_size_mm(), background_hex().
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def resource_path(relative: str = "") -> Path:
    """Return path to a bundled resource file.
    
    Works both in development (project root) and when frozen with PyInstaller.
    """
    import sys
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        # In development, project root is two levels up from this file
        base = Path(__file__).resolve().parent.parent
    if relative:
        return base / relative
    return base


def user_data_dir() -> Path:
    """Return (and create) the writable app data folder.
    
    %APPDATA%/PassportPhotoApp on Windows.
    """
    import os
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    folder = appdata / "PassportPhotoApp"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ---------------------------------------------------------------------------
# Photo / Paper / Background lookup tables
# ---------------------------------------------------------------------------

PHOTO_SIZES: Dict[str, Tuple[float, float]] = {
    "20x25": (20.0, 25.0),
    "25x30": (25.0, 30.0),
    "25x35": (25.0, 35.0),
    "35x35": (35.0, 35.0),
    "35x45": (35.0, 45.0),
    "33x48": (33.0, 48.0),
    "51x51": (51.0, 51.0),
    "50x70": (50.0, 70.0),
}

PAPER_SIZES: Dict[str, Tuple[float, float]] = {
    "4x6":  (101.6, 152.4),
    "5x7":  (127.0, 177.8),
    "A4":   (210.0, 297.0),
    "A5":   (148.0, 210.0),
    "Letter": (215.9, 279.4),
}

BACKGROUND_COLORS: Dict[str, str] = {
    "white":      "#FFFFFF",
    "light_blue": "#D6EAF8",
    "blue":       "#1A5FAB",
    "red":        "#DC3545",
    "light_grey": "#E8E8E8",
    "custom":     "#FFFFFF",
}


def photo_size_mm(key: str) -> Tuple[float, float]:
    """Return (width_mm, height_mm) for a photo size key like '35x45'."""
    if key in PHOTO_SIZES:
        return PHOTO_SIZES[key]
    # Try parsing 'WxH' format
    try:
        parts = key.lower().split("x")
        return (float(parts[0]), float(parts[1]))
    except (ValueError, IndexError):
        raise ValueError(f"Unknown photo size: {key}")


def paper_size_mm(key: str) -> Tuple[float, float]:
    """Return (width_mm, height_mm) for a paper size key like '4x6' or 'A4'."""
    if key in PAPER_SIZES:
        return PAPER_SIZES[key]
    try:
        parts = key.lower().split("x")
        return (float(parts[0]) * 25.4, float(parts[1]) * 25.4)
    except (ValueError, IndexError):
        raise ValueError(f"Unknown paper size: {key}")


def background_hex(key: str) -> str:
    """Return hex color string for a background color key."""
    if key.startswith("#") and len(key) in (4, 7, 9):
        return key
    return BACKGROUND_COLORS.get(key, "#FFFFFF")


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: Dict[str, Any] = {
    "first_run_done": False,
    "shop_name": "",
    "photo_size": "35x45",
    "paper_size": "4x6",
    "copies": 8,
    "dpi": 300,
    "gap_mm": 2.0,
    "margin_mm": 5.0,
    "cut_lines": True,
    "background": "white",
    "custom_bg_color": "#FFFFFF",
    "camera_index": 0,
    "printer_name": "",
    "brightness": 0,
    "contrast": 0,
    "warmth": 0,
    "shadow_lift": 0,
    "head_ratio": 0.75,
    "auto_enhance": True,
    "paper_orientation": "auto",
    "output_format": "png",
    "jpg_quality": 95,
    "save_outputs": True,
    "last_preset": "",
    "app_version": "1.0.0",
}


# ---------------------------------------------------------------------------
# SettingsManager
# ---------------------------------------------------------------------------

class SettingsManager:
    """Load, save, and access application settings.
    
    Settings are stored in %APPDATA%/PassportPhotoApp/settings.json.
    Missing keys are filled from DEFAULT_SETTINGS automatically.
    """

    _instance: Optional["SettingsManager"] = None

    def __new__(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._path = user_data_dir() / "settings.json"
        self.load()
        self._loaded = True

    # -- persistence --------------------------------------------------------

    def load(self) -> None:
        """Load settings from disk, merging with defaults."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._settings.update(data)
                    logger.info("Settings loaded from %s", self._path)
                else:
                    logger.warning("Settings file has invalid format, using defaults")
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read settings (%s), using defaults", exc)
                # Back up the corrupted file
                backup = self._path.with_suffix(".json.bak")
                try:
                    shutil.copy2(self._path, backup)
                    logger.info("Backed up corrupted settings to %s", backup)
                except OSError:
                    pass
        else:
            logger.info("No settings file found, using defaults")
        # Ensure all default keys exist
        for key, value in DEFAULT_SETTINGS.items():
            self._settings.setdefault(key, value)

    def save(self) -> None:
        """Save current settings to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            logger.info("Settings saved to %s", self._path)
        except OSError as exc:
            logger.error("Could not save settings: %s", exc)

    # -- access -------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save."""
        self._settings[key] = value
        self.save()

    def update(self, values: Dict[str, Any]) -> None:
        """Update multiple settings at once and save."""
        self._settings.update(values)
        self.save()

    def all(self) -> Dict[str, Any]:
        """Return a copy of all settings."""
        return dict(self._settings)

    @property
    def path(self) -> Path:
        """Path to the settings file."""
        return self._path

    # -- convenience --------------------------------------------------------

    def get_photo_size_mm(self) -> Tuple[float, float]:
        """Return current photo size in mm."""
        return photo_size_mm(self.get("photo_size", "35x45"))

    def get_paper_size_mm(self) -> Tuple[float, float]:
        """Return current paper size in mm."""
        return paper_size_mm(self.get("paper_size", "4x6"))

    def get_background_hex(self) -> str:
        """Return current background color as hex."""
        bg = self.get("background", "white")
        if bg == "custom":
            return self.get("custom_bg_color", "#FFFFFF")
        return background_hex(bg)

    # -- presets ------------------------------------------------------------

    def load_presets(self) -> list:
        """Load presets from config/presets.json."""
        presets_path = resource_path("config/presets.json")
        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("presets", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load presets: %s", exc)
            return []

    def apply_preset(self, preset: Dict[str, Any]) -> None:
        """Apply a preset's values to current settings."""
        mapping = {
            "photo_size": "photo_size",
            "paper_size": "paper_size",
            "copies": "copies",
            "dpi": "dpi",
            "background": "background",
        }
        updates = {}
        for preset_key, settings_key in mapping.items():
            if preset_key in preset:
                updates[settings_key] = preset[preset_key]
        if updates:
            self.update(updates)
            logger.info("Applied preset: %s", preset.get("name", "unknown"))

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None
