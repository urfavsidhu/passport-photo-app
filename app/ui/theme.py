"""Theme manager for Passport Photo App.

Provides synchronized Minimalist Glassmorphism SaaS Dashboard themes:
- Deep obsidian and pearlescent ambient gradients.
- Translucent frosted glass Bento Grid cards with specular highlights.
- Luminous cyan and emerald glow accents.
- Dynamic adaptation to Windows default color scheme (Light/Dark).
- Untinted photo previews and swatches.
"""

import logging
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Dark Glassmorphism SaaS Palette (Deep Obsidian + Frosted Slate + Luminous Cyan)
DARK_THEME: Dict[str, str] = {
    "window": "#0B101B",
    "window_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #080C14, stop:0.4 #0E1524, stop:1 #0A111F)",
    "panel": "rgba(20, 28, 44, 0.72)",
    "panel_solid": "#131A29",
    "panel_alt": "rgba(28, 38, 58, 0.60)",
    "border": "rgba(255, 255, 255, 0.08)",
    "border_highlight": "rgba(255, 255, 255, 0.16)",
    "badge_bg": "rgba(56, 189, 248, 0.10)",
    "badge_border": "rgba(56, 189, 248, 0.22)",
    "badge_text": "#38BDF8",
    "button": "rgba(255, 255, 255, 0.06)",
    "button_hover": "rgba(255, 255, 255, 0.11)",
    "button_pressed": "rgba(255, 255, 255, 0.03)",
    "text": "#F8FAFC",
    "text_muted": "#94A3B8",
    "text_dark": "#0F172A",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "success": "#10B981",
    "success_hover": "#059669",
    "cta_gradient_process": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669)",
    "cta_gradient_process_hover": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34D399, stop:1 #10B981)",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "cta_gradient_save": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #3B82F6)",
    "danger": "#EF4444",
    "danger_hover": "#DC2626",
    "banner_bg": "rgba(239, 68, 68, 0.14)",
    "banner_border": "rgba(239, 68, 68, 0.45)",
    "banner_text": "#FCA5A5",
    "warn_bg": "rgba(245, 158, 11, 0.14)",
    "warn_border": "rgba(245, 158, 11, 0.45)",
    "warn_text": "#FCD34D",
    "slider_groove": "rgba(255, 255, 255, 0.10)",
    "slider_active": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8)",
    "slider_handle": "#FFFFFF",
    "slider_handle_border": "#0284C7",
    "input_bg": "rgba(13, 19, 31, 0.72)",
    "input_border": "rgba(255, 255, 255, 0.09)",
    "input_focus_border": "#38BDF8",
    "scrollbar_bg": "transparent",
    "scrollbar_handle": "rgba(255, 255, 255, 0.16)",
}

# Light Glassmorphism SaaS Palette (Frosted Pearl + Pure White Glass + Obsidian Accents)
LIGHT_THEME: Dict[str, str] = {
    "window": "#EEF2F6",
    "window_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F8FAFC, stop:0.5 #EEF2F6, stop:1 #E2E8F0)",
    "panel": "rgba(255, 255, 255, 0.92)",
    "panel_solid": "#FFFFFF",
    "panel_alt": "rgba(241, 245, 249, 0.85)",
    "border": "rgba(0, 0, 0, 0.07)",
    "border_highlight": "rgba(255, 255, 255, 0.98)",
    "badge_bg": "rgba(2, 132, 199, 0.08)",
    "badge_border": "rgba(2, 132, 199, 0.20)",
    "badge_text": "#0284C7",
    "button": "rgba(255, 255, 255, 0.88)",
    "button_hover": "#FFFFFF",
    "button_pressed": "#E2E8F0",
    "text": "#181B20",
    "text_muted": "#64748B",
    "text_dark": "#FFFFFF",
    "accent": "#0284C7",
    "accent_hover": "#0369A1",
    "success": "#059669",
    "success_hover": "#047857",
    "cta_gradient_process": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981)",
    "cta_gradient_process_hover": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669)",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "cta_gradient_save": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB)",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "banner_bg": "rgba(254, 242, 242, 0.95)",
    "banner_border": "rgba(239, 68, 68, 0.40)",
    "banner_text": "#991B1B",
    "warn_bg": "rgba(255, 251, 235, 0.95)",
    "warn_border": "rgba(245, 158, 11, 0.40)",
    "warn_text": "#92400E",
    "slider_groove": "#E2E8F0",
    "slider_active": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8)",
    "slider_handle": "#FFFFFF",
    "slider_handle_border": "#0284C7",
    "input_bg": "rgba(255, 255, 255, 0.95)",
    "input_border": "rgba(0, 0, 0, 0.12)",
    "input_focus_border": "#0284C7",
    "scrollbar_bg": "transparent",
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

    palette.setColor(QPalette.ColorRole.Window, QColor(t["panel_solid"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["panel_solid"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["panel_solid"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["panel_solid"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["panel_solid"]))
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

    disabled_btn_bg = "rgba(255, 255, 255, 0.04)" if is_dark else "#F1F5F9"
    disabled_btn_border = "rgba(255, 255, 255, 0.06)" if is_dark else "#E2E8F0"
    disabled_btn_text = "#475569" if is_dark else "#94A3B8"

    # Minimalist Bento SaaS elements
    if is_dark:
        sidebar_bg = "rgba(22, 27, 34, 0.92)"
        nav_active_bg = "#23272F"
        nav_active_color = "#38BDF8"
        nav_active_border = "1px solid rgba(56, 189, 248, 0.35)"
        upload_btn_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8)"
        upload_btn_text = "#080C14"
        upload_btn_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #0284C7)"
        preset_card_bg = "rgba(20, 28, 44, 0.72)"
        preset_card_border = "rgba(255, 255, 255, 0.08)"
        preset_card_top_border = "rgba(255, 255, 255, 0.16)"
        preset_card_badge_bg = "rgba(56, 189, 248, 0.10)"
        preset_card_badge_border = "rgba(56, 189, 248, 0.22)"
        preset_card_badge_text = "#38BDF8"
        preset_combo_bg = "rgba(13, 19, 31, 0.72)"
        preset_combo_color = "#F8FAFC"
        preset_combo_border = "rgba(255, 255, 255, 0.12)"
        pill_tag_bg = "rgba(255, 255, 255, 0.06)"
        pill_tag_text = "#F8FAFC"
        pill_tag_border = "rgba(255, 255, 255, 0.12)"
        pill_tag_hover = "rgba(255, 255, 255, 0.16)"
    else:
        # Light mode matching reference image (iDraft style high-contrast obsidian elements)
        sidebar_bg = "rgba(255, 255, 255, 0.95)"
        nav_active_bg = "#181B20"
        nav_active_color = "#FFFFFF"
        nav_active_border = "none"
        upload_btn_bg = "#181B20"
        upload_btn_text = "#FFFFFF"
        upload_btn_hover = "#2D3139"
        preset_card_bg = "#181B20"
        preset_card_border = "#23272F"
        preset_card_top_border = "#2D333B"
        preset_card_badge_bg = "rgba(255, 255, 255, 0.14)"
        preset_card_badge_border = "rgba(255, 255, 255, 0.22)"
        preset_card_badge_text = "#FFFFFF"
        preset_combo_bg = "#232832"
        preset_combo_color = "#FFFFFF"
        preset_combo_border = "rgba(255, 255, 255, 0.22)"
        pill_tag_bg = "rgba(255, 255, 255, 0.12)"
        pill_tag_text = "#FFFFFF"
        pill_tag_border = "rgba(255, 255, 255, 0.20)"
        pill_tag_hover = "rgba(255, 255, 255, 0.26)"

    return f"""
QWidget {{
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
    color: {t["text"]};
    background-color: transparent;
}}

QMainWindow, QDialog, QWizard {{
    background: {t["window_gradient"]};
}}

/* SaaS Navigation Rail (iDraft Bento Style) */
QFrame#sidebarRail {{
    background-color: {sidebar_bg};
    border: 1px solid {t["border"]};
    border-top: 1px solid {t["border_highlight"]};
    border-radius: 18px;
}}

QLabel#sidebarBrand {{
    font-size: 14px;
    font-weight: 800;
    color: {t["text"]};
    letter-spacing: 0.8px;
    padding-left: 4px;
}}

QLabel#sidebarBrandSub {{
    font-size: 10px;
    font-weight: 700;
    color: {t["text_muted"]};
    padding-left: 4px;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}}

QPushButton#navItem {{
    background-color: transparent;
    color: {t["text_muted"]};
    border: none;
    border-radius: 12px;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
    min-height: 38px;
}}
QPushButton#navItem:hover {{
    background-color: {t["button_hover"]};
    color: {t["text"]};
}}

QPushButton#navItemActive {{
    background-color: {nav_active_bg};
    color: {nav_active_color};
    border: {nav_active_border};
    border-radius: 12px;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 700;
    min-height: 38px;
}}

QLabel#sidebarShopBadge {{
    background-color: {t["badge_bg"]};
    border: 1px solid {t["badge_border"]};
    border-radius: 8px;
    color: {t["badge_text"]};
    font-size: 11px;
    font-weight: 700;
    padding: 6px 10px;
}}

/* Dashboard Header */
QFrame#dashboardHeader {{
    background-color: transparent;
    border: none;
}}
QLabel#dashboardTitle {{
    font-size: 20px;
    font-weight: 800;
    color: {t["text"]};
    letter-spacing: -0.3px;
}}
QLabel#dashboardSubtitle {{
    font-size: 12px;
    font-weight: 500;
    color: {t["text_muted"]};
}}

/* Top SaaS CTA Button (+ Upload Photo) */
QPushButton#uploadBtn {{
    background: {upload_btn_bg};
    color: {upload_btn_text};
    font-size: 13px;
    font-weight: 700;
    border-radius: 20px;
    padding: 8px 22px;
    min-height: 40px;
    border: none;
}}
QPushButton#uploadBtn:hover {{
    background: {upload_btn_hover};
}}

QPushButton#adjustCropBtn {{
    border-radius: 20px;
    padding: 8px 18px;
    min-height: 40px;
    font-weight: 600;
}}

/* Hero Bento Preview Card */
QFrame#heroCanvasCard {{
    background-color: {t["panel"]};
    border: 1px solid {t["border"]};
    border-top: 1px solid {t["border_highlight"]};
    border-radius: 18px;
}}

/* Top Action Buttons & General SaaS Buttons */
QPushButton {{
    background-color: {t["button"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-top: 1px solid {t["border_highlight"]};
    border-radius: 9px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 38px;
}}
QPushButton:hover {{
    background-color: {t["button_hover"]};
    border-color: {t["accent"]};
}}
QPushButton:pressed {{
    background-color: {t["button_pressed"]};
}}
QPushButton:checked {{
    background-color: {t["accent"]};
    color: #FFFFFF;
    border-color: {t["accent"]};
    font-weight: bold;
}}
QPushButton:disabled {{
    background-color: {disabled_btn_bg};
    border-color: {disabled_btn_border};
    color: {disabled_btn_text};
}}

/* Primary Big Actions (Luminous SaaS CTAs) */
QPushButton#processBtn {{
    background: {t["cta_gradient_process"]};
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 700;
    min-height: 48px;
    padding: 10px 24px;
    border: none;
    border-radius: 10px;
}}
QPushButton#processBtn:hover {{
    background: {t["cta_gradient_process_hover"]};
}}
QPushButton#processBtn:disabled {{
    background-color: {disabled_btn_bg};
    color: {disabled_btn_text};
    border: 1px solid {disabled_btn_border};
}}

QPushButton#printBtn {{
    background: {t["cta_gradient_process"]};
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 700;
    min-height: 48px;
    padding: 10px 24px;
    border: none;
    border-radius: 10px;
}}
QPushButton#printBtn:hover {{
    background: {t["cta_gradient_process_hover"]};
}}
QPushButton#printBtn:disabled {{
    background-color: {disabled_btn_bg};
    color: {disabled_btn_text};
    border: 1px solid {disabled_btn_border};
}}

QPushButton#saveBtn {{
    background: {t["cta_gradient_save"]};
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 700;
    min-height: 44px;
    padding: 10px 22px;
    border: none;
    border-radius: 10px;
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
    border: 1px solid {t["border"]};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    min-height: 34px;
}}
QPushButton[role="danger"]:hover {{
    background-color: {t["danger"]};
    color: #FFFFFF;
    border-color: {t["danger"]};
}}

/* Floating Alert Banners (SaaS Pill Notice) */
QFrame#bannerFrame {{
    background-color: {t["banner_bg"]};
    border: 1.5px solid {t["banner_border"]};
    border-radius: 10px;
}}
QLabel#bannerLabel {{
    color: {t["banner_text"]};
    font-weight: bold;
    font-size: 13px;
}}

QFrame#warnFrame {{
    background-color: {t["warn_bg"]};
    border: 1.5px solid {t["warn_border"]};
    border-radius: 10px;
}}
QLabel#warnLabel {{
    color: {t["warn_text"]};
    font-weight: bold;
    font-size: 13px;
}}

QLabel {{
    color: {t["text"]};
    font-size: 13px;
    padding: 2px;
}}
QLabel#statusLabel {{
    font-size: 12px;
    color: {t["text_muted"]};
    padding: 4px 6px;
    background-color: transparent;
}}
QLabel#previewPlaceholder {{
    color: {t["text_muted"]};
    font-size: 14px;
    background-color: {t["panel"]};
    border: 1.5px dashed {t["border_highlight"]};
    border-radius: 14px;
}}

/* Bento Grid Cards (Frosted Glass with Specular Edge) */
QGroupBox {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: {t["badge_text"]};
    background-color: {t["panel"]};
    border: 1px solid {t["border"]};
    border-top: 1px solid {t["border_highlight"]};
    border-radius: 18px;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    margin-left: 10px;
    padding: 2px 10px;
    background-color: {t["badge_bg"]};
    border: 1px solid {t["badge_border"]};
    border-radius: 6px;
    color: {t["badge_text"]};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

/* Preset Bento Card (High Contrast Obsidian Card) */
QGroupBox#presetBentoCard {{
    background-color: {preset_card_bg};
    border: 1px solid {preset_card_border};
    border-top: 1px solid {preset_card_top_border};
    border-radius: 18px;
    color: {preset_card_badge_text};
}}
QGroupBox#presetBentoCard::title {{
    background-color: {preset_card_badge_bg};
    border: 1px solid {preset_card_badge_border};
    border-radius: 6px;
    color: {preset_card_badge_text};
}}
QGroupBox#presetBentoCard QComboBox {{
    background-color: {preset_combo_bg};
    color: {preset_combo_color};
    border: 1px solid {preset_combo_border};
}}
QGroupBox#presetBentoCard QComboBox QAbstractItemView {{
    background-color: {preset_combo_bg};
    color: {preset_combo_color};
}}

QPushButton[pillTag="true"] {{
    background-color: {pill_tag_bg};
    color: {pill_tag_text};
    border: 1px solid {pill_tag_border};
    border-radius: 14px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    min-height: 28px;
}}
QPushButton[pillTag="true"]:hover {{
    background-color: {pill_tag_hover};
}}

/* Glass Inputs & Dropdowns */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {t["input_bg"]};
    border: 1px solid {t["input_border"]};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 36px;
    color: {t["text"]};
}}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {{
    border-color: {t["accent"]};
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border: 1.5px solid {t["input_focus_border"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {t["panel_solid"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {t["badge_bg"]};
    selection-color: {t["accent"]};
    color: {t["text"]};
}}

/* Minimalist SaaS Sliders */
QSlider::groove:horizontal {{
    height: 5px;
    background: {t["slider_groove"]};
    border-radius: 2.5px;
}}
QSlider::sub-page:horizontal {{
    background: {t["slider_active"]};
    border-radius: 2.5px;
}}
QSlider::handle:horizontal {{
    background: {t["slider_handle"]};
    border: 2px solid {t["slider_handle_border"]};
    width: 16px;
    height: 16px;
    margin: -5.5px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {t["accent"]};
    border-color: #FFFFFF;
}}

/* Progress Bar */
QProgressBar {{
    background-color: {t["panel"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    height: 18px;
    text-align: center;
    font-size: 11px;
    color: {t["text"]};
}}
QProgressBar::chunk {{
    background: {t["slider_active"]};
    border-radius: 7px;
}}

/* Top Menu Bar */
QMenuBar {{
    background-color: transparent;
    border: none;
    padding: 4px;
    font-size: 13px;
    color: {t["text_muted"]};
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 6px;
    background-color: transparent;
    color: {t["text"]};
}}
QMenuBar::item:selected {{
    background-color: {t["button"]};
    color: {t["accent"]};
}}
QMenu {{
    background-color: {t["panel_solid"]};
    border: 1px solid {t["border"]};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 6px;
    color: {t["text"]};
}}
QMenu::item:selected {{
    background-color: {t["button"]};
    color: {t["accent"]};
}}

/* Tooltips */
QToolTip {{
    background-color: {t["panel_solid"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* Scroll Area */
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t["scrollbar_handle"]};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t["accent"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {t["panel"]};
    border-top: 1px solid {t["border"]};
    font-size: 12px;
    color: {t["text_muted"]};
    padding: 4px 12px;
}}

/* Checkbox */
QCheckBox {{
    font-size: 13px;
    spacing: 8px;
    padding: 4px;
    color: {t["text"]};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {t["input_border"]};
    border-radius: 5px;
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
    border: 1.5px solid {t["border_highlight"]};
    border-radius: 8px;
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
    mode_str = "Dark Obsidian Glass" if is_dark else "Light Pearl Glass"
    logger.info("Applied %s theme (Minimalist Glassmorphism SaaS)", mode_str)


def setup_theme_listener(app: QApplication) -> None:
    """Connect to live Windows light/dark color scheme changes."""
    try:
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda scheme: apply_theme(app))
            logger.info("Connected to live colorSchemeChanged signals")
    except Exception as exc:
        logger.debug("Live theme change listener skipped: %s", exc)
