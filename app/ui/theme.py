"""Theme manager for Passport Photo App.

Provides synchronized modern Dark Slate and Light Slate themes:
- Dynamically adapts to Windows default color scheme (Light/Dark).
- Identical card-based architecture with rounded corners (10px).
- Clean alignments, vibrant sky-blue accented sliders, and high-contrast action buttons.
- Untinted photo previews and swatches.
"""

import logging
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Dark Slate Navy Palette (exact match to user reference screenshot)
DARK_THEME: Dict[str, str] = {
    "window": "#161C26",
    "panel": "#1E2634",
    "panel_alt": "#243042",
    "border": "#2D384A",
    "border_light": "#3E4D64",
    "button": "#2D3748",
    "button_hover": "#374358",
    "button_pressed": "#202937",
    "text": "#F1F5F9",
    "text_muted": "#94A3B8",
    "text_dark": "#0F172A",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "success": "#16A34A",
    "success_hover": "#15803D",
    "success_pressed": "#166534",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "danger": "#EF4444",
    "danger_hover": "#DC2626",
    "banner_bg": "#351518",
    "banner_border": "#EF4444",
    "banner_text": "#FCA5A5",
    "warn_bg": "#332610",
    "warn_border": "#F59E0B",
    "warn_text": "#FCD34D",
    "slider_groove": "#283344",
    "slider_active": "#38BDF8",
    "slider_handle": "#94A3B8",
    "slider_handle_border": "#CBD5E1",
    "input_bg": "#141A23",
    "input_border": "#2D384A",
    "input_focus_border": "#38BDF8",
    "scrollbar_bg": "#161C26",
    "scrollbar_handle": "#2E3A4D",
}

# Light Slate Card Palette (clean, modern light equivalent)
LIGHT_THEME: Dict[str, str] = {
    "window": "#F1F5F9",
    "panel": "#FFFFFF",
    "panel_alt": "#F8FAFC",
    "border": "#E2E8F0",
    "border_light": "#CBD5E1",
    "button": "#F8FAFC",
    "button_hover": "#F1F5F9",
    "button_pressed": "#E2E8F0",
    "text": "#0F172A",
    "text_muted": "#64748B",
    "text_dark": "#FFFFFF",
    "accent": "#0284C7",
    "accent_hover": "#0369A1",
    "success": "#16A34A",
    "success_hover": "#15803D",
    "success_pressed": "#166534",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "banner_bg": "#FEF2F2",
    "banner_border": "#EF4444",
    "banner_text": "#991B1B",
    "warn_bg": "#FFFBEB",
    "warn_border": "#F59E0B",
    "warn_text": "#92400E",
    "slider_groove": "#E2E8F0",
    "slider_active": "#0284C7",
    "slider_handle": "#FFFFFF",
    "slider_handle_border": "#0284C7",
    "input_bg": "#FFFFFF",
    "input_border": "#CBD5E1",
    "input_focus_border": "#0284C7",
    "scrollbar_bg": "#F1F5F9",
    "scrollbar_handle": "#CBD5E1",
}


def detect_scheme(app: Optional[QApplication] = None) -> bool:
    """Return True if Windows is in dark mode, False if light mode."""
    try:
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorScheme"):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
    except Exception:
        pass

    if app is not None:
        try:
            return app.palette().window().color().lightness() < 128
        except Exception:
            pass
    return False


def build_palette(is_dark: bool) -> QPalette:
    """Create a Qt QPalette matching the active theme for native dialogs."""
    t = DARK_THEME if is_dark else LIGHT_THEME
    palette = QPalette()

    palette.setColor(QPalette.ColorRole.Window, QColor(t["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["input_bg"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["panel_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["text_dark"]))

    disabled_text = QColor(t["text_muted"])
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)

    return palette


def get_stylesheet(is_dark: bool) -> str:
    """Render the master QSS template for the active theme mode."""
    t = DARK_THEME if is_dark else LIGHT_THEME

    disabled_btn_bg = "#1A222D" if is_dark else "#F1F5F9"
    disabled_btn_border = "#252F3F" if is_dark else "#E2E8F0"
    disabled_btn_text = "#475569" if is_dark else "#94A3B8"

    return f"""
QWidget {{
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 14px;
    color: {t["text"]};
    background-color: transparent;
}}

QMainWindow, QDialog, QWizard {{
    background-color: {t["window"]};
}}

QPushButton {{
    background-color: {t["button"]};
    color: {t["text"]};
    border: 1px solid {t["border_light"]};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 600;
    min-height: 38px;
}}
QPushButton:hover {{
    background-color: {t["button_hover"]};
    border-color: {t["border_light"]};
}}
QPushButton:pressed {{
    background-color: {t["button_pressed"]};
}}
QPushButton:checked {{
    background-color: {t["accent"]};
    color: {t["text_dark"]};
    border-color: {t["accent"]};
    font-weight: bold;
}}
QPushButton:disabled {{
    background-color: {disabled_btn_bg};
    border-color: {disabled_btn_border};
    color: {disabled_btn_text};
}}

QPushButton#processBtn, QPushButton#printBtn {{
    background-color: {t["success"]};
    color: #FFFFFF;
    font-size: 16px;
    font-weight: bold;
    min-height: 48px;
    padding: 10px 24px;
    border: none;
    border-radius: 8px;
}}
QPushButton#processBtn:hover, QPushButton#printBtn:hover {{
    background-color: {t["success_hover"]};
}}
QPushButton#processBtn:disabled, QPushButton#printBtn:disabled {{
    background-color: {disabled_btn_bg};
    color: {disabled_btn_text};
    border: 1px solid {disabled_btn_border};
}}

QPushButton#saveBtn {{
    background-color: {t["primary"]};
    color: #FFFFFF;
    font-size: 15px;
    font-weight: bold;
    min-height: 44px;
    padding: 10px 24px;
    border: none;
    border-radius: 8px;
}}
QPushButton#saveBtn:hover {{
    background-color: {t["primary_hover"]};
}}
QPushButton#saveBtn:disabled {{
    background-color: {disabled_btn_bg};
    color: {disabled_btn_text};
    border: 1px solid {disabled_btn_border};
}}

QPushButton[role="danger"] {{
    background-color: {t["button"]};
    color: {t["danger"]};
    border: 1px solid {t["border_light"]};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
    min-height: 34px;
}}
QPushButton[role="danger"]:hover {{
    background-color: {t["danger"]};
    color: #FFFFFF;
}}

QFrame#bannerFrame {{
    background-color: {t["banner_bg"]};
    border: 1.5px solid {t["banner_border"]};
    border-radius: 8px;
}}
QLabel#bannerLabel {{
    color: {t["banner_text"]};
    font-weight: bold;
    font-size: 14px;
}}

QFrame#warnFrame {{
    background-color: {t["warn_bg"]};
    border: 1.5px solid {t["warn_border"]};
    border-radius: 8px;
}}
QLabel#warnLabel {{
    color: {t["warn_text"]};
    font-weight: bold;
    font-size: 14px;
}}

QLabel {{
    color: {t["text"]};
    font-size: 14px;
    padding: 2px;
}}
QLabel#titleLabel {{
    font-size: 22px;
    font-weight: bold;
    color: {t["text"]};
    padding: 8px 0px;
}}
QLabel#statusLabel {{
    font-size: 13px;
    color: {t["text_muted"]};
    padding: 4px 6px;
    background-color: transparent;
}}
QLabel#previewPlaceholder {{
    color: {t["text_muted"]};
    font-size: 15px;
    background-color: {t["panel"]};
    border: 1.5px dashed {t["border_light"]};
    border-radius: 10px;
}}

QGroupBox {{
    font-size: 14px;
    font-weight: bold;
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    background-color: {t["panel"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 1px 8px;
    background-color: {t["window"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    color: {t["text"]};
}}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {t["input_bg"]};
    border: 1px solid {t["input_border"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 14px;
    min-height: 36px;
    color: {t["text"]};
}}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {{
    border-color: {t["border_light"]};
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border-color: {t["input_focus_border"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox QAbstractItemView {{
    background-color: {t["panel"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {t["panel_alt"]};
    selection-color: {t["accent"]};
    color: {t["text"]};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {t["slider_groove"]};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {t["slider_active"]};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {t["slider_handle"]};
    border: 2px solid {t["slider_handle_border"]};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    background: {t["panel"]};
    border-color: {t["accent"]};
}}

QProgressBar {{
    background-color: {t["panel"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    height: 20px;
    text-align: center;
    font-size: 12px;
    color: {t["text"]};
}}
QProgressBar::chunk {{
    background-color: {t["accent"]};
    border-radius: 7px;
}}

QMenuBar {{
    background-color: {t["window"]};
    border: none;
    padding: 4px;
    font-size: 14px;
    color: {t["text_muted"]};
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 4px;
    background-color: transparent;
    color: {t["text"]};
}}
QMenuBar::item:selected {{
    background-color: {t["button"]};
    color: {t["accent"]};
}}
QMenu {{
    background-color: {t["panel"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
    color: {t["text"]};
}}
QMenu::item:selected {{
    background-color: {t["button"]};
    color: {t["accent"]};
}}

QToolTip {{
    background-color: {t["panel"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: {t["scrollbar_bg"]};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {t["scrollbar_handle"]};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t["border_light"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QStatusBar {{
    background-color: {t["panel"]};
    border-top: 1px solid {t["border"]};
    font-size: 13px;
    color: {t["text_muted"]};
    padding: 4px;
}}

QCheckBox {{
    font-size: 14px;
    spacing: 8px;
    padding: 4px;
    color: {t["text"]};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {t["input_border"]};
    border-radius: 4px;
    background-color: {t["input_bg"]};
}}
QCheckBox::indicator:checked {{
    background-color: {t["accent"]};
    border-color: {t["accent"]};
}}
QCheckBox::indicator:hover {{
    border-color: {t["accent"]};
}}

QFrame#colorPreview {{
    border: 1px solid {t["border_light"]};
    border-radius: 6px;
    min-width: 50px;
    min-height: 36px;
}}
"""


def apply_theme(app: QApplication, is_dark: Optional[bool] = None) -> None:
    """Apply the active theme mode (palette + Fusion style + QSS) to the application."""
    if is_dark is None:
        is_dark = detect_scheme(app)

    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    palette = build_palette(is_dark)
    app.setPalette(palette)

    qss = get_stylesheet(is_dark)
    app.setStyleSheet(qss)
    mode_str = "Dark Slate" if is_dark else "Light Slate"
    logger.info("Applied %s theme (system matching)", mode_str)


def setup_theme_listener(app: QApplication) -> None:
    """Connect to live Windows light/dark color scheme changes."""
    try:
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda scheme: apply_theme(app))
            logger.info("Connected to live colorSchemeChanged signals")
    except Exception as exc:
        logger.debug("Live theme change listener skipped: %s", exc)
