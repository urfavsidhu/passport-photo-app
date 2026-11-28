"""First-run setup wizard and settings editor.

Multi-page wizard for configuring shop name, camera, printer,
photo/paper size, margins, background color, lighting defaults,
printer calibration, and customer file retention.
Reusable from the Settings menu.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QCheckBox, QSlider, QFrame, QMessageBox,
    QColorDialog, QGroupBox, QWidget,
)

from app.settings_manager import (
    SettingsManager, PHOTO_SIZES, PAPER_SIZES, BACKGROUND_COLORS,
)

logger = logging.getLogger(__name__)


class SetupWizard(QWizard):
    """Setup wizard for first run and settings editing.

    Signals:
        settings_saved: Emitted when the wizard finishes and saves settings.
    """

    settings_saved = Signal()

    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("Passport Photo App — Setup & Settings")
        self.setMinimumSize(720, 600)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Add pages
        self._shop_page = ShopNamePage(settings)
        self._device_page = DeviceSelectionPage(settings)
        self._size_page = SizeSettingsPage(settings)
        self._bg_page = BackgroundColorPage(settings)
        self._lighting_page = LightingDefaultsPage(settings)

        self.addPage(self._shop_page)
        self.addPage(self._device_page)
        self.addPage(self._size_page)
        self.addPage(self._bg_page)
        self.addPage(self._lighting_page)

        self.setButtonText(QWizard.WizardButton.FinishButton, "Save Settings")
        finish_btn = self.button(QWizard.WizardButton.FinishButton)
        if finish_btn:
            finish_btn.setProperty("role", "success")

        cancel_btn = self.button(QWizard.WizardButton.CancelButton)
        if cancel_btn:
            cancel_btn.setProperty("role", "danger")

        self.finished.connect(self._on_finish)

    def _on_finish(self, result: int) -> None:
        """Save settings when wizard finishes or record first run on close."""
        if result == QWizard.DialogCode.Accepted:
            all_updates = {}
            all_updates.update(self._shop_page.get_values())
            all_updates.update(self._device_page.get_values())
            all_updates.update(self._size_page.get_values())
            all_updates.update(self._bg_page.get_values())
            all_updates.update(self._lighting_page.get_values())
            all_updates["first_run_done"] = True
            self._settings.update(all_updates)
            logger.info("Setup wizard completed, settings saved")
            self.settings_saved.emit()
        else:
            # P1-10: wizard cancelled still sets first_run_done so it doesn't loop
            self._settings.set("first_run_done", True)
            logger.info("Setup wizard closed/cancelled, first_run_done set to True")


# ---------------------------------------------------------------------------
# Page 1: Shop Name
# ---------------------------------------------------------------------------

class ShopNamePage(QWizardPage):
    """Page 1: Shop name."""

    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self.setTitle("Welcome to Passport Photo App!")
        self.setSubTitle("Configure your shop details. This takes less than a minute.")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        welcome = QLabel(
            "This app automatically removes backgrounds, crops to exact passport dimensions, "
            "optimizes lighting, and arranges multiple copies on photo paper for instant 1-click printing."
        )
        welcome.setWordWrap(True)
        layout.addWidget(welcome)

        form = QFormLayout()
        form.setSpacing(12)
        self._shop_name = QLineEdit()
        self._shop_name.setPlaceholderText("e.g. Apna CSC Digital Seva Kendra")
        self._shop_name.setText(settings.get("shop_name", ""))
        form.addRow("Shop Name:", self._shop_name)
        layout.addLayout(form)
        layout.addStretch()

    def get_values(self) -> dict:
        return {"shop_name": self._shop_name.text().strip()}

    def save(self) -> None:
        self._settings.update(self.get_values())


# ---------------------------------------------------------------------------
# Page 2: Camera & Printer Selection
# ---------------------------------------------------------------------------

class DeviceSelectionPage(QWizardPage):
    """Page 2: Camera and printer selection."""

    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self.setTitle("Camera & Printer Selection")
        self.setSubTitle("Select your default devices. You can also upload photos from disk without a camera.")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Camera group
        cam_group = QGroupBox("Webcam / Camera")
        cam_layout = QHBoxLayout(cam_group)
        self._camera_combo = QComboBox()
        self._camera_combo.addItem("No camera (file upload only)", -1)
        cam_layout.addWidget(self._camera_combo, stretch=1)

        self._refresh_cam_btn = QPushButton("Refresh")
        self._refresh_cam_btn.setFixedWidth(100)
        self._refresh_cam_btn.clicked.connect(self._refresh_cameras)
        cam_layout.addWidget(self._refresh_cam_btn)

        self._test_cam_btn = QPushButton("Test")
        self._test_cam_btn.setFixedWidth(80)
        self._test_cam_btn.clicked.connect(self._test_camera)
        cam_layout.addWidget(self._test_cam_btn)

        layout.addWidget(cam_group)

        # Printer group
        prn_group = QGroupBox("Photo Printer")
        prn_layout = QHBoxLayout(prn_group)
        self._printer_combo = QComboBox()
        prn_layout.addWidget(self._printer_combo, stretch=1)

        self._refresh_prn_btn = QPushButton("Refresh")
        self._refresh_prn_btn.setFixedWidth(100)
        self._refresh_prn_btn.clicked.connect(self._refresh_printers)
        prn_layout.addWidget(self._refresh_prn_btn)

        layout.addWidget(prn_group)

        # Printer calibration group
        cal_group = QGroupBox("Printer Calibration (Optional - For Scale / Margin Correction)")
        cal_form = QFormLayout(cal_group)
        cal_form.setSpacing(8)

        scale_box = QHBoxLayout()
        self._cal_scale_x = QDoubleSpinBox()
        self._cal_scale_x.setRange(0.80, 1.20)
        self._cal_scale_x.setSingleStep(0.005)
        self._cal_scale_x.setDecimals(4)
        self._cal_scale_x.setValue(settings.get("calibration_scale_x", 1.0))

        self._cal_scale_y = QDoubleSpinBox()
        self._cal_scale_y.setRange(0.80, 1.20)
        self._cal_scale_y.setSingleStep(0.005)
        self._cal_scale_y.setDecimals(4)
        self._cal_scale_y.setValue(settings.get("calibration_scale_y", 1.0))

        scale_box.addWidget(QLabel("Scale X:"))
        scale_box.addWidget(self._cal_scale_x)
        scale_box.addWidget(QLabel("Scale Y:"))
        scale_box.addWidget(self._cal_scale_y)
        cal_form.addRow("Scale Multipliers:", scale_box)

        offset_box = QHBoxLayout()
        self._cal_offset_x = QDoubleSpinBox()
        self._cal_offset_x.setRange(-20.0, 20.0)
        self._cal_offset_x.setSingleStep(0.5)
        self._cal_offset_x.setSuffix(" mm")
        self._cal_offset_x.setValue(settings.get("calibration_offset_x_mm", 0.0))

        self._cal_offset_y = QDoubleSpinBox()
        self._cal_offset_y.setRange(-20.0, 20.0)
        self._cal_offset_y.setSingleStep(0.5)
        self._cal_offset_y.setSuffix(" mm")
        self._cal_offset_y.setValue(settings.get("calibration_offset_y_mm", 0.0))

        offset_box.addWidget(QLabel("Offset X:"))
        offset_box.addWidget(self._cal_offset_x)
        offset_box.addWidget(QLabel("Offset Y:"))
        offset_box.addWidget(self._cal_offset_y)
        cal_form.addRow("Physical Offsets:", offset_box)

        layout.addWidget(cal_group)
        layout.addStretch()

        self._refresh_cameras()
        self._refresh_printers()

    def _refresh_cameras(self) -> None:
        self._camera_combo.clear()
        self._camera_combo.addItem("No camera (file upload only)", -1)
        try:
            from app.camera.capture import list_cameras
            cameras = list_cameras()
            for idx, name in cameras:
                self._camera_combo.addItem(name, idx)
            saved = self._settings.get("camera_index", 0)
            for i in range(self._camera_combo.count()):
                if self._camera_combo.itemData(i) == saved:
                    self._camera_combo.setCurrentIndex(i)
                    break
        except Exception as exc:
            logger.warning("Could not list cameras: %s", exc)

    def _test_camera(self) -> None:
        idx = self._camera_combo.currentData()
        if idx is None or idx == -1:
            QMessageBox.information(self, "Camera", "No camera selected.")
            return
        try:
            from app.camera.capture import CameraCapture
            cam = CameraCapture(idx)
            cam.open()
            frame = cam.grab_frame()
            cam.close()
            if frame:
                QMessageBox.information(
                    self,
                    "Camera Test",
                    f"Camera {idx} connected successfully!\nResolution: {frame.size[0]}x{frame.size[1]} px"
                )
            else:
                QMessageBox.warning(self, "Camera Test", "Camera connected but could not capture a frame.")
        except Exception as exc:
            QMessageBox.warning(self, "Camera Test", f"Camera test failed:\n{exc}")

    def _refresh_printers(self) -> None:
        self._printer_combo.clear()
        self._printer_combo.addItem("No printer (Save PDF / PNG only)", "")
        try:
            from app.printing.printer import list_printers, get_default_printer
            printers = list_printers()
            default = get_default_printer()
            for name in printers:
                label = f"{name} (Default)" if name == default else name
                self._printer_combo.addItem(label, name)
            saved = self._settings.get("printer_name", "")
            for i in range(self._printer_combo.count()):
                data = self._printer_combo.itemData(i)
                if data == saved or (not saved and data == default):
                    self._printer_combo.setCurrentIndex(i)
                    break
        except Exception as exc:
            logger.warning("Could not list printers: %s", exc)

    def get_values(self) -> dict:
        cam_idx = self._camera_combo.currentData()
        prn_name = self._printer_combo.currentData()
        return {
            "camera_index": cam_idx if cam_idx is not None else -1,
            "printer_name": prn_name if prn_name else "",
            "calibration_scale_x": self._cal_scale_x.value(),
            "calibration_scale_y": self._cal_scale_y.value(),
            "calibration_offset_x_mm": self._cal_offset_x.value(),
            "calibration_offset_y_mm": self._cal_offset_y.value(),
        }

    def save(self) -> None:
        self._settings.update(self.get_values())


# ---------------------------------------------------------------------------
# Page 3: Photo & Paper Size
# ---------------------------------------------------------------------------

class SizeSettingsPage(QWizardPage):
    """Page 3: Photo size, paper size, copies, DPI, gap, margins, cut lines."""

    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self.setTitle("Passport Size & Print Sheet Layout")
        self.setSubTitle("Configure default paper size, photo dimensions, margins, and cut lines.")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        # Photo size
        self._photo_size = QComboBox()
        for key in PHOTO_SIZES:
            w, h = PHOTO_SIZES[key]
            self._photo_size.addItem(f"{key}  ({w:.0f} × {h:.0f} mm)", key)
        self._select_combo(self._photo_size, settings.get("photo_size", "35x45"))
        form.addRow("Photo Dimensions:", self._photo_size)

        # Paper size
        self._paper_size = QComboBox()
        for key in PAPER_SIZES:
            w, h = PAPER_SIZES[key]
            self._paper_size.addItem(f"{key}  ({w:.0f} × {h:.0f} mm)", key)
        self._select_combo(self._paper_size, settings.get("paper_size", "4x6"))
        form.addRow("Paper Size:", self._paper_size)

        # Copies
        self._copies = QSpinBox()
        self._copies.setRange(1, 100)
        self._copies.setValue(settings.get("copies", 8))
        form.addRow("Default Copies:", self._copies)

        # DPI
        self._dpi = QComboBox()
        for val in [150, 300, 600]:
            self._dpi.addItem(f"{val} DPI", val)
        self._select_combo(self._dpi, settings.get("dpi", 300))
        form.addRow("Print DPI:", self._dpi)

        # Orientation
        self._orientation = QComboBox()
        for val, label in [("auto", "Auto (Fit Maximum Photos)"), ("portrait", "Portrait"), ("landscape", "Landscape")]:
            self._orientation.addItem(label, val)
        self._select_combo(self._orientation, settings.get("paper_orientation", "auto"))
        form.addRow("Sheet Orientation:", self._orientation)

        # Gap
        self._gap = QDoubleSpinBox()
        self._gap.setRange(0, 20)
        self._gap.setSingleStep(0.5)
        self._gap.setSuffix(" mm")
        self._gap.setValue(settings.get("gap_mm", 2.0))
        form.addRow("Gap Between Photos:", self._gap)

        # Outer Margin
        self._margin = QDoubleSpinBox()
        self._margin.setRange(0, 30)
        self._margin.setSingleStep(1.0)
        self._margin.setSuffix(" mm")
        self._margin.setValue(settings.get("margin_mm", 5.0))
        form.addRow("Outer Page Margin:", self._margin)

        # Minimum Printer Margin (Hardware Limit)
        self._min_margin = QDoubleSpinBox()
        self._min_margin.setRange(1.0, 15.0)
        self._min_margin.setSingleStep(0.5)
        self._min_margin.setSuffix(" mm")
        self._min_margin.setValue(settings.get("min_printer_margin_mm", 3.0))
        self._min_margin.setToolTip("Physical hardware unprintable margin. Layout will never place photos closer than this.")
        form.addRow("Hardware Minimum Margin:", self._min_margin)

        # Cut lines
        self._cut_lines = QCheckBox("Print light grey corner crop/cut marks")
        self._cut_lines.setChecked(settings.get("cut_lines", True))
        form.addRow("", self._cut_lines)

        layout.addLayout(form)

        # Preset box
        preset_group = QGroupBox("Load Common Preset")
        preset_layout = QHBoxLayout(preset_group)
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("Select a preset...", None)
        presets = settings.load_presets()
        for p in presets:
            self._preset_combo.addItem(p["name"], p)
        preset_layout.addWidget(self._preset_combo, stretch=1)

        apply_btn = QPushButton("Apply Preset")
        apply_btn.setFixedWidth(120)
        apply_btn.clicked.connect(self._apply_preset)
        preset_layout.addWidget(apply_btn)

        layout.addWidget(preset_group)
        layout.addStretch()

    def _select_combo(self, combo: QComboBox, value) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _apply_preset(self) -> None:
        preset = self._preset_combo.currentData()
        if preset is None:
            return
        if "photo_size" in preset:
            self._select_combo(self._photo_size, preset["photo_size"])
        if "paper_size" in preset:
            self._select_combo(self._paper_size, preset["paper_size"])
        if "copies" in preset:
            self._copies.setValue(preset["copies"])
        if "dpi" in preset:
            self._select_combo(self._dpi, preset["dpi"])

    def get_values(self) -> dict:
        return {
            "photo_size": self._photo_size.currentData(),
            "paper_size": self._paper_size.currentData(),
            "copies": self._copies.value(),
            "dpi": self._dpi.currentData(),
            "paper_orientation": self._orientation.currentData(),
            "gap_mm": self._gap.value(),
            "margin_mm": self._margin.value(),
            "min_printer_margin_mm": self._min_margin.value(),
            "cut_lines": self._cut_lines.isChecked(),
        }

    def save(self) -> None:
        self._settings.update(self.get_values())


# ---------------------------------------------------------------------------
# Page 4: Background Color
# ---------------------------------------------------------------------------

class BackgroundColorPage(QWizardPage):
    """Page 4: Background color selection."""

    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self._custom_color = settings.get("custom_bg_color", "#FFFFFF")

        self.setTitle("Default Background Color")
        self.setSubTitle("Choose the default background color to fill behind the subject.")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        self._bg_combo = QComboBox()
        for key, hex_val in BACKGROUND_COLORS.items():
            if key == "custom":
                self._bg_combo.addItem("Custom Color...", key)
            else:
                self._bg_combo.addItem(f"{key.replace('_', ' ').title()}  ({hex_val})", key)
        self._select_combo(self._bg_combo, settings.get("background", "white"))
        self._bg_combo.currentIndexChanged.connect(self._on_color_changed)
        layout.addWidget(QLabel("Background Color:"))
        layout.addWidget(self._bg_combo)

        custom_layout = QHBoxLayout()
        self._custom_btn = QPushButton("Pick Custom Color")
        self._custom_btn.setFixedHeight(40)
        self._custom_btn.clicked.connect(self._pick_custom_color)
        self._custom_btn.setEnabled(settings.get("background") == "custom")
        custom_layout.addWidget(self._custom_btn)

        self._color_preview = QFrame()
        self._color_preview.setObjectName("colorPreview")
        self._color_preview.setFixedSize(60, 40)
        self._update_preview()
        custom_layout.addWidget(self._color_preview)
        custom_layout.addStretch()

        layout.addLayout(custom_layout)

        info = QLabel(
            "• Standard Indian Passport / Visa: White\n"
            "• Many Government / Exam Forms: Light Blue (#D6EAF8)\n"
            "• Special formats: Light Grey or Custom"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

    def _select_combo(self, combo: QComboBox, value) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _on_color_changed(self) -> None:
        self._custom_btn.setEnabled(self._bg_combo.currentData() == "custom")
        self._update_preview()

    def _pick_custom_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._custom_color), self, "Pick Custom Background Color"
        )
        if color.isValid():
            self._custom_color = color.name()
            self._update_preview()

    def _update_preview(self) -> None:
        key = self._bg_combo.currentData()
        if key == "custom":
            hex_color = self._custom_color
        else:
            from app.settings_manager import background_hex
            hex_color = background_hex(key) if key else "#FFFFFF"
        self._color_preview.setStyleSheet(
            f"background-color: {hex_color}; border: 2px solid #CDB59A; border-radius: 6px;"
        )

    def get_values(self) -> dict:
        return {
            "background": self._bg_combo.currentData(),
            "custom_bg_color": self._custom_color,
        }

    def save(self) -> None:
        self._settings.update(self.get_values())


# ---------------------------------------------------------------------------
# Page 5: Lighting Defaults & Customer Privacy
# ---------------------------------------------------------------------------

class LightingDefaultsPage(QWizardPage):
    """Page 5: Lighting defaults, head height ratio, and customer privacy retention."""

    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self.setTitle("Lighting, Proportions & Customer Privacy")
        self.setSubTitle("Set default lighting enhancements, head height ratio, and file retention.")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._auto_enhance = QCheckBox("Enable Auto-Enhance by default (Gentle CLAHE & Exposure)")
        self._auto_enhance.setChecked(settings.get("auto_enhance", False))
        layout.addWidget(self._auto_enhance)

        form = QFormLayout()
        form.setSpacing(10)

        self._brightness = self._make_slider("Brightness", settings.get("brightness", 0))
        form.addRow("Brightness:", self._brightness["layout"])

        self._contrast = self._make_slider("Contrast", settings.get("contrast", 0))
        form.addRow("Contrast:", self._contrast["layout"])

        self._warmth = self._make_slider("Warmth:", settings.get("warmth", 0))
        form.addRow("Warmth:", self._warmth["layout"])

        self._shadow = self._make_slider("Shadow Lift:", settings.get("shadow_lift", 0))
        form.addRow("Shadow Lift:", self._shadow["layout"])

        layout.addLayout(form)

        head_layout = QHBoxLayout()
        head_layout.addWidget(QLabel("Head Size Ratio:"))
        self._head_ratio = QDoubleSpinBox()
        self._head_ratio.setRange(0.50, 0.90)
        self._head_ratio.setSingleStep(0.05)
        self._head_ratio.setValue(settings.get("head_ratio", 0.75))
        self._head_ratio.setToolTip("Head height proportion in the final photo (standard is 0.70 - 0.80)")
        head_layout.addWidget(self._head_ratio)
        head_layout.addWidget(QLabel("(Default 0.75 = 75% of photo height)"))
        head_layout.addStretch()
        layout.addLayout(head_layout)

        # Privacy and Storage Options
        privacy_group = QGroupBox("Customer Privacy & File Retention")
        privacy_layout = QFormLayout(privacy_group)
        privacy_layout.setSpacing(10)

        self._output_format = QComboBox()
        self._output_format.addItem("PNG (Lossless - Recommended)", "png")
        self._output_format.addItem("JPEG (High Quality)", "jpg")
        saved_fmt = settings.get("output_format", "png")
        for i in range(self._output_format.count()):
            if self._output_format.itemData(i) == saved_fmt:
                self._output_format.setCurrentIndex(i)
        privacy_layout.addRow("Save Format:", self._output_format)

        self._keep_days = QSpinBox()
        self._keep_days.setRange(0, 365)
        self._keep_days.setValue(settings.get("keep_saved_days", 0))
        self._keep_days.setToolTip("0 = Don't retain customer prints (cleaned up immediately for customer privacy).")
        privacy_layout.addRow("Keep Saved Files For (Days):", self._keep_days)

        self._save_outputs = QCheckBox("Save copy to Documents/PassportPhotoApp/Output on Print/Save")
        self._save_outputs.setChecked(settings.get("save_outputs", False))
        privacy_layout.addRow("", self._save_outputs)

        layout.addWidget(privacy_group)
        layout.addStretch()

    def _make_slider(self, name: str, value: int) -> dict:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(value)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(50)

        label = QLabel(f"{value}")
        label.setFixedWidth(40)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        slider.valueChanged.connect(lambda v: label.setText(str(v)))

        layout.addWidget(slider, stretch=1)
        layout.addWidget(label)

        return {"layout": widget, "slider": slider, "label": label}

    def get_values(self) -> dict:
        return {
            "auto_enhance": self._auto_enhance.isChecked(),
            "brightness": self._brightness["slider"].value(),
            "contrast": self._contrast["slider"].value(),
            "warmth": self._warmth["slider"].value(),
            "shadow_lift": self._shadow["slider"].value(),
            "head_ratio": self._head_ratio.value(),
            "output_format": self._output_format.currentData(),
            "save_outputs": self._save_outputs.isChecked(),
            "keep_saved_days": self._keep_days.value(),
        }

    def save(self) -> None:
        self._settings.update(self.get_values())
