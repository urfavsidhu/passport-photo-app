"""Main application window for Passport Photo App.

Provides the primary interface for daily CSC shop operations:
- 1-click automatic workflow upon upload/camera capture
- Big buttons, clear high-contrast controls
- Non-blocking asynchronous processing with QThread and dirty re-run queue
- Fast slider tweaking using cached AI cutouts
- Strict blocking banners and safety checks for defect-free printing
- Interactive crop adjustment tool
- Direct physical-size printing and multi-format sheet export
"""

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMenuBar,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QStatusBar, QVBoxLayout, QWidget,
)
from PIL import Image

from app.core.pipeline import PassportPipeline, PipelineResult
from app.settings_manager import (
    BACKGROUND_COLORS, PAPER_SIZES, PHOTO_SIZES, SettingsManager,
    background_hex, cleanup_old_saved_files, resource_path, user_output_dir,
)
from app.ui.adjust_crop_dialog import AdjustCropDialog
from app.ui.preview_panel import PreviewPanel
from app.ui.setup_wizard import SetupWizard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background Camera Prober Thread (non-blocking)
# ---------------------------------------------------------------------------

class CameraProbeWorker(QThread):
    """Probes available cameras in the background to avoid freezing the UI on startup."""
    cameras_found = Signal(list)

    def run(self) -> None:
        try:
            from app.camera.capture import list_cameras
            cams = list_cameras()
            self.cameras_found.emit(cams)
        except Exception as exc:
            logger.warning("Background camera probe failed: %s", exc)
            self.cameras_found.emit([])


# ---------------------------------------------------------------------------
# Worker Thread for Heavy Pipeline Operations
# ---------------------------------------------------------------------------

class PipelineWorker(QThread):
    """Background worker for pipeline runs (AI background removal, crop, layout)."""

    progress_signal = Signal(str, int)       # step description, percentage
    finished_signal = Signal(object)         # PipelineResult
    error_signal = Signal(str)               # friendly error message

    def __init__(
        self,
        pipeline: PassportPipeline,
        image: Optional[Image.Image],
        settings: Dict[str, Any],
        is_reapply: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.image = image
        self.settings = settings
        self.is_reapply = is_reapply

    def run(self) -> None:
        try:
            if self.is_reapply and self.pipeline.has_cached_data():
                # Fast branch: re-apply enhancement and layout without AI model
                self.progress_signal.emit("Updating photo enhancements...", 30)
                self.pipeline.reapply_enhancements(self.settings)
                self.progress_signal.emit("Re-building sheet layout...", 70)
                result = self.pipeline.reapply_crop_and_layout(self.settings)
                self.progress_signal.emit("Ready!", 100)
                self.finished_signal.emit(result)
            else:
                if self.image is None:
                    raise ValueError("No image provided for processing.")
                result = self.pipeline.run(
                    self.image,
                    self.settings,
                    progress_callback=lambda step, pct: self.progress_signal.emit(step, pct),
                )
                self.finished_signal.emit(result)
        except Exception as exc:
            logger.exception("Pipeline worker encountered error: %s", exc)
            self.error_signal.emit(str(exc))


# ---------------------------------------------------------------------------
# Camera Dialog
# ---------------------------------------------------------------------------

class CameraCaptureDialog(QDialog):
    """Modal dialog for capturing a live photo from webcam."""

    def __init__(self, camera_index: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.camera_index = camera_index
        self.captured_image: Optional[Image.Image] = None
        self._cam = None
        self._timer = QTimer(self)

        self.setWindowTitle("Camera Capture")
        self.setMinimumSize(640, 520)
        self._setup_ui()
        self._start_camera()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.preview_label = QLabel("Connecting to camera...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setObjectName("cameraPreview")
        self.preview_label.setMinimumSize(600, 400)
        layout.addWidget(self.preview_label, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.capture_btn = QPushButton("📷 Capture Photo")
        self.capture_btn.setFixedHeight(48)
        self.capture_btn.setProperty("role", "success")
        self.capture_btn.clicked.connect(self._on_capture)
        btn_layout.addWidget(self.capture_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(48)
        self.cancel_btn.setProperty("role", "danger")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _start_camera(self) -> None:
        try:
            from app.camera.capture import CameraCapture
            self._cam = CameraCapture(self.camera_index)
            self._cam.open()
            self._timer.timeout.connect(self._update_frame)
            self._timer.start(33)  # ~30 FPS
        except Exception as exc:
            logger.error("Camera open error: %s", exc)
            QMessageBox.warning(
                self,
                "Camera Error",
                f"Could not open camera {self.camera_index}.\n"
                f"Please ensure it is connected and not being used by another application.\n\n"
                f"Details: {exc}",
            )
            QTimer.singleShot(100, self.reject)

    def _update_frame(self) -> None:
        if self._cam and self._cam.is_open:
            frame = self._cam.grab_frame()
            if frame:
                from app.ui.preview_panel import pil_to_qpixmap
                pix = pil_to_qpixmap(frame, max_size=800)
                scaled = pix.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)

    def _on_capture(self) -> None:
        if self._cam and self._cam.is_open:
            self.captured_image = self._cam.grab_frame()
            self._cleanup()
            self.accept()

    def _cleanup(self) -> None:
        self._timer.stop()
        if self._cam:
            self._cam.close()
            self._cam = None

    def closeEvent(self, event) -> None:
        self._cleanup()
        super().closeEvent(event)

    def reject(self) -> None:
        self._cleanup()
        super().reject()


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Main window for Passport Photo App."""

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings = settings_manager
        self.pipeline = PassportPipeline()

        self.current_image: Optional[Image.Image] = None
        self.latest_result: Optional[PipelineResult] = None
        self.worker: Optional[PipelineWorker] = None

        # Dirty worker mechanism to prevent dropped UI adjustments
        self._pending_pipeline_run: bool = False
        self._pending_full_run: bool = False

        # Debounce timer for slider adjustments
        self._slider_timer = QTimer(self)
        self._slider_timer.setSingleShot(True)
        self._slider_timer.setInterval(300)
        self._slider_timer.timeout.connect(self._trigger_fast_reapply)

        # Background camera probe
        self._probe_worker: Optional[CameraProbeWorker] = None

        self._init_window()
        self._create_menu()
        self._setup_ui()
        self._load_settings_into_ui()
        self._check_camera_setting()

        # Run privacy cleanup on start
        cleanup_old_saved_files(keep_days=self.settings.get("keep_saved_days", 0))

    def _init_window(self) -> None:
        shop_title = self.settings.get("shop_name", "").strip()
        if shop_title:
            self.setWindowTitle(f"Passport Photo App — {shop_title}")
        else:
            self.setWindowTitle("Passport Photo App (CSC Digital Seva)")

        self.setMinimumSize(1150, 780)
        self.setAcceptDrops(True)

        icon_path = resource_path("assets/icon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _create_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Photo...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_upload_clicked)
        file_menu.addAction(open_action)

        cam_action = QAction("&Camera Capture...", self)
        cam_action.setShortcut("Ctrl+Shift+C")
        cam_action.triggered.connect(self._on_camera_clicked)
        file_menu.addAction(cam_action)

        file_menu.addSeparator()

        save_action = QAction("&Save Sheets (PDF/PNG)...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_sheet_clicked)
        file_menu.addAction(save_action)

        print_action = QAction("&Print Sheets...", self)
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        print_action.triggered.connect(self._on_print_clicked)
        file_menu.addAction(print_action)

        file_menu.addSeparator()

        cal_action = QAction("&Print Calibration Sheet...", self)
        cal_action.triggered.connect(self._print_calibration_sheet)
        file_menu.addAction(cal_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        settings_menu = menubar.addMenu("&Settings")
        setup_action = QAction("&Configuration Wizard...", self)
        setup_action.triggered.connect(self._open_settings_wizard)
        settings_menu.addAction(setup_action)

        settings_cal_action = QAction("&Printer Calibration...", self)
        settings_cal_action.triggered.connect(self._print_calibration_sheet)
        settings_menu.addAction(settings_cal_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About Passport Photo App", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left Column: Banners, Actions, Image Preview & Before/After
        left_box = QVBoxLayout()
        left_box.setSpacing(10)

        # Red Blocking Banner (Defects / Unsafe Photo)
        self.banner_frame = QFrame()
        self.banner_frame.setObjectName("bannerFrame")
        self.banner_frame.setVisible(False)
        banner_layout = QVBoxLayout(self.banner_frame)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(6)

        self.banner_label = QLabel()
        self.banner_label.setObjectName("bannerLabel")
        self.banner_label.setWordWrap(True)
        banner_layout.addWidget(self.banner_label)

        self.confirm_defect_cb = QCheckBox(
            "I understand this photo has defects and confirm I want to print/save anyway."
        )
        self.confirm_defect_cb.setObjectName("confirmDefectCheckbox")
        self.confirm_defect_cb.toggled.connect(self._on_defect_confirmation_toggled)
        banner_layout.addWidget(self.confirm_defect_cb)

        left_box.addWidget(self.banner_frame)

        # Amber Warning Banner (Non-blocking notices, e.g. multiple faces)
        self.warn_frame = QFrame()
        self.warn_frame.setObjectName("warnFrame")
        self.warn_frame.setVisible(False)
        warn_layout = QVBoxLayout(self.warn_frame)
        warn_layout.setContentsMargins(12, 8, 12, 8)
        warn_layout.setSpacing(4)

        self.warn_label = QLabel()
        self.warn_label.setObjectName("warnLabel")
        self.warn_label.setWordWrap(True)
        warn_layout.addWidget(self.warn_label)

        left_box.addWidget(self.warn_frame)

        # Action Buttons Header
        top_btn_layout = QHBoxLayout()
        top_btn_layout.setSpacing(12)

        self.upload_btn = QPushButton("📁 Upload Photo")
        self.upload_btn.setObjectName("uploadBtn")
        self.upload_btn.setToolTip("Select photo from computer (JPG, PNG, WEBP)")
        self.upload_btn.clicked.connect(self._on_upload_clicked)
        top_btn_layout.addWidget(self.upload_btn)

        self.camera_btn = QPushButton("📷 Live Camera")
        self.camera_btn.setObjectName("cameraBtn")
        self.camera_btn.setToolTip("Capture photo directly using webcam")
        self.camera_btn.clicked.connect(self._on_camera_clicked)
        top_btn_layout.addWidget(self.camera_btn)

        self.adjust_crop_btn = QPushButton("✂️ Adjust Crop...")
        self.adjust_crop_btn.setObjectName("adjustCropBtn")
        self.adjust_crop_btn.setToolTip("Fine-tune crop area and position manually")
        self.adjust_crop_btn.setEnabled(False)
        self.adjust_crop_btn.clicked.connect(self._on_adjust_crop_clicked)
        top_btn_layout.addWidget(self.adjust_crop_btn)

        left_box.addLayout(top_btn_layout)

        # Preview Widget
        self.preview_panel = PreviewPanel(self)
        left_box.addWidget(self.preview_panel, stretch=1)

        # Progress bar & status line
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_box.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready. Select or drop a photo to begin.")
        self.status_label.setObjectName("statusLabel")
        left_box.addWidget(self.status_label)

        main_layout.addLayout(left_box, stretch=3)

        # Right Column: Controls & Settings in ScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(390)
        scroll.setMaximumWidth(470)

        right_widget = QWidget()
        right_box = QVBoxLayout(right_widget)
        right_box.setContentsMargins(10, 8, 18, 14)
        right_box.setSpacing(14)

        # Preset Selector
        preset_group = QGroupBox("📋 Quick Document Presets")
        preset_layout = QVBoxLayout(preset_group)
        preset_layout.setContentsMargins(14, 18, 14, 14)
        self.preset_combo = QComboBox()
        self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setMinimumContentsLength(16)
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preset_combo.setMinimumHeight(38)
        self.preset_combo.addItem("Select standard size...", None)
        for p in self.settings.load_presets():
            self.preset_combo.addItem(p["name"], p)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.preset_combo)
        right_box.addWidget(preset_group)

        # Background Group
        bg_group = QGroupBox("🎨 Background Color")
        bg_layout = QGridLayout(bg_group)
        bg_layout.setContentsMargins(14, 18, 14, 14)
        bg_layout.setHorizontalSpacing(10)
        bg_layout.setVerticalSpacing(12)
        bg_layout.setColumnStretch(0, 0)
        bg_layout.setColumnStretch(1, 1)
        bg_layout.setColumnStretch(2, 0)

        lbl_color = QLabel("Color:")
        lbl_color.setFixedWidth(55)
        bg_layout.addWidget(lbl_color, 0, 0)

        self.bg_combo = QComboBox()
        self.bg_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.bg_combo.setMinimumContentsLength(10)
        self.bg_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.bg_combo.setMinimumHeight(38)
        for k, v in BACKGROUND_COLORS.items():
            if k == "custom":
                self.bg_combo.addItem("Custom Color...", k)
            else:
                self.bg_combo.addItem(f"{k.replace('_', ' ').title()}", k)
        self.bg_combo.currentIndexChanged.connect(self._on_bg_changed)
        bg_layout.addWidget(self.bg_combo, 0, 1)

        self.color_preview = QFrame()
        self.color_preview.setObjectName("colorPreview")
        self.color_preview.setFixedSize(54, 38)
        bg_layout.addWidget(self.color_preview, 0, 2)

        self.custom_color_btn = QPushButton("Pick Color")
        self.custom_color_btn.setFixedHeight(38)
        self.custom_color_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.custom_color_btn.clicked.connect(self._on_pick_custom_color)
        bg_layout.addWidget(self.custom_color_btn, 1, 0, 1, 3)

        right_box.addWidget(bg_group)

        # Photo & Print Layout Group (&& prevents mnemonic underscore on P)
        size_group = QGroupBox("📐 Photo Size && Print Copies")
        size_layout = QGridLayout(size_group)
        size_layout.setContentsMargins(14, 18, 14, 14)
        size_layout.setHorizontalSpacing(10)
        size_layout.setVerticalSpacing(12)
        size_layout.setColumnStretch(0, 0)
        size_layout.setColumnStretch(1, 1)

        lbl_photo_size = QLabel("Photo Size:")
        lbl_photo_size.setFixedWidth(135)
        size_layout.addWidget(lbl_photo_size, 0, 0)

        self.photo_size_combo = QComboBox()
        self.photo_size_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.photo_size_combo.setMinimumContentsLength(10)
        self.photo_size_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.photo_size_combo.setMinimumHeight(38)
        for k, (w, h) in PHOTO_SIZES.items():
            self.photo_size_combo.addItem(f"{k} mm ({w:.0f}x{h:.0f})", k)
        self.photo_size_combo.currentIndexChanged.connect(self._on_photo_size_changed)
        size_layout.addWidget(self.photo_size_combo, 0, 1)

        lbl_paper_size = QLabel("Paper Size:")
        lbl_paper_size.setFixedWidth(135)
        size_layout.addWidget(lbl_paper_size, 1, 0)

        self.paper_size_combo = QComboBox()
        self.paper_size_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.paper_size_combo.setMinimumContentsLength(10)
        self.paper_size_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.paper_size_combo.setMinimumHeight(38)
        for k, (w, h) in PAPER_SIZES.items():
            self.paper_size_combo.addItem(f"{k} ({w:.0f}x{h:.0f} mm)", k)
        self.paper_size_combo.currentIndexChanged.connect(self._on_paper_size_changed)
        size_layout.addWidget(self.paper_size_combo, 1, 1)

        lbl_copies = QLabel("Number of Copies:")
        lbl_copies.setFixedWidth(135)
        size_layout.addWidget(lbl_copies, 2, 0)

        self.copies_spin = QSpinBox()
        self.copies_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.copies_spin.setMinimumHeight(38)
        self.copies_spin.setRange(1, 100)
        self.copies_spin.setValue(self.settings.get("copies", 8))
        self.copies_spin.valueChanged.connect(self._on_copies_changed)
        size_layout.addWidget(self.copies_spin, 2, 1)

        right_box.addWidget(size_group)

        # Lighting Adjustments Group (&& prevents mnemonic underscore on T)
        light_group = QGroupBox("💡 Lighting && Touch-up")
        light_layout = QVBoxLayout(light_group)
        light_layout.setContentsMargins(14, 18, 14, 14)
        light_layout.setSpacing(10)

        self.auto_enhance_btn = QPushButton("✨ Auto Enhance: OFF")
        self.auto_enhance_btn.setCheckable(True)
        self.auto_enhance_btn.setChecked(self.settings.get("auto_enhance", False))
        self.auto_enhance_btn.setMinimumHeight(38)
        self.auto_enhance_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.auto_enhance_btn.clicked.connect(self._on_auto_enhance_toggle)
        light_layout.addWidget(self.auto_enhance_btn)

        self.slider_bright = self._create_slider("Brightness", -100, 100, self.settings.get("brightness", 0), light_layout)
        self.slider_contrast = self._create_slider("Contrast", -100, 100, self.settings.get("contrast", 0), light_layout)
        self.slider_warmth = self._create_slider("Warmth (Color Temp)", -100, 100, self.settings.get("warmth", 0), light_layout)
        self.slider_shadow = self._create_slider("Shadow Lift", 0, 100, self.settings.get("shadow_lift", 0), light_layout)

        reset_btn = QPushButton("↺ Reset Sliders")
        reset_btn.setFixedHeight(36)
        reset_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        reset_btn.setProperty("role", "danger")
        reset_btn.clicked.connect(self._reset_lighting_sliders)
        light_layout.addWidget(reset_btn)

        right_box.addWidget(light_group)

        # Primary Action Buttons
        act_box = QVBoxLayout()
        act_box.setContentsMargins(0, 6, 0, 6)
        act_box.setSpacing(12)

        self.process_btn = QPushButton("⚡ Process Photo")
        self.process_btn.setObjectName("processBtn")
        self.process_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.process_btn.setProperty("role", "success")
        self.process_btn.clicked.connect(self._on_process_clicked)
        act_box.addWidget(self.process_btn)

        self.print_btn = QPushButton("🖨️ Print Sheets")
        self.print_btn.setObjectName("printBtn")
        self.print_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.print_btn.setProperty("role", "success")
        self.print_btn.clicked.connect(self._on_print_clicked)
        self.print_btn.setEnabled(False)
        act_box.addWidget(self.print_btn)

        self.save_btn = QPushButton("💾 Save Sheet (PDF / PNG)")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.save_btn.setProperty("role", "success")
        self.save_btn.clicked.connect(self._on_save_sheet_clicked)
        self.save_btn.setEnabled(False)
        act_box.addWidget(self.save_btn)

        right_box.addLayout(act_box)
        right_box.addStretch()

        scroll.setWidget(right_widget)
        main_layout.addWidget(scroll, stretch=2)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select photo to begin.")

    def _create_slider(
        self, label_text: str, min_val: int, max_val: int, default_val: int, parent_layout: QVBoxLayout
    ) -> QSlider:
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 2, 0, 2)
        box.setSpacing(2)

        head = QHBoxLayout()
        lbl = QLabel(label_text)
        val_lbl = QLabel(f"{default_val}")
        val_lbl.setFixedWidth(36)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        head.addWidget(lbl)
        head.addStretch()
        head.addWidget(val_lbl)
        box.addLayout(head)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
        slider.valueChanged.connect(self._on_slider_moved)
        box.addWidget(slider)

        parent_layout.addWidget(container)
        return slider

    def _load_settings_into_ui(self) -> None:
        # Photo size
        ps = self.settings.get("photo_size", "35x45")
        for i in range(self.photo_size_combo.count()):
            if self.photo_size_combo.itemData(i) == ps:
                self.photo_size_combo.setCurrentIndex(i)
                break

        # Paper size
        paper = self.settings.get("paper_size", "4x6")
        for i in range(self.paper_size_combo.count()):
            if self.paper_size_combo.itemData(i) == paper:
                self.paper_size_combo.setCurrentIndex(i)
                break

        # Copies
        self.copies_spin.setValue(self.settings.get("copies", 8))

        # Background
        bg = self.settings.get("background", "white")
        for i in range(self.bg_combo.count()):
            if self.bg_combo.itemData(i) == bg:
                self.bg_combo.setCurrentIndex(i)
                break
        self._update_color_preview()

        # Sliders
        self.slider_bright.setValue(self.settings.get("brightness", 0))
        self.slider_contrast.setValue(self.settings.get("contrast", 0))
        self.slider_warmth.setValue(self.settings.get("warmth", 0))
        self.slider_shadow.setValue(self.settings.get("shadow_lift", 0))

        # Auto enhance
        ae = self.settings.get("auto_enhance", False)
        self.auto_enhance_btn.setChecked(ae)
        self.auto_enhance_btn.setText(f"✨ Auto Enhance: {'ON' if ae else 'OFF'}")

    def _check_camera_setting(self) -> None:
        cam_idx = self.settings.get("camera_index", 0)
        if cam_idx == -1:
            self.camera_btn.setEnabled(False)
            self.camera_btn.setToolTip("Camera is disabled in Settings")
        else:
            self.camera_btn.setEnabled(True)
            self.camera_btn.setToolTip("Capture photo directly using webcam")

    # -----------------------------------------------------------------------
    # Drag and Drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                suffix = Path(url.toLocalFile()).suffix.lower()
                if suffix in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.exists() and path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                self._load_image_file(path)
                event.acceptProposedAction()
                break

    # -----------------------------------------------------------------------
    # Image Ingestion & One-Click Execution
    # -----------------------------------------------------------------------

    def _on_upload_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Photo",
            "",
            "Image Files (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*.*)",
        )
        if path:
            self._load_image_file(Path(path))

    def _on_camera_clicked(self) -> None:
        cam_idx = self.settings.get("camera_index", 0)
        if cam_idx < 0:
            QMessageBox.information(self, "Camera Disabled", "Camera capture is disabled in Settings.")
            return
        dialog = CameraCaptureDialog(cam_idx, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.captured_image:
            self.current_image = dialog.captured_image
            self.preview_panel.set_before_image(self.current_image)
            self.status_label.setText("Photo captured. Processing automatically...")
            self._start_pipeline(full_run=True)

    def _load_image_file(self, path: Path) -> None:
        try:
            img = Image.open(path)
            self.current_image = img.copy()
            img.close()
            self.preview_panel.set_before_image(self.current_image)
            self.status_label.setText(f"Loaded: {path.name}. Running 1-Click Process...")
            self.status_bar.showMessage(f"Loaded {path.name}")
            # Reset defect confirm checkbox
            self.confirm_defect_cb.setChecked(False)
            self._start_pipeline(full_run=True)
        except Exception as exc:
            logger.error("Failed to load image %s: %s", path, exc)
            QMessageBox.critical(self, "Image Load Error", f"Could not open image:\n{exc}")

    # -----------------------------------------------------------------------
    # Pipeline Execution & Race Condition Resolution
    # -----------------------------------------------------------------------

    def _on_process_clicked(self) -> None:
        if self.current_image is None:
            QMessageBox.information(self, "No Photo", "Please upload or capture a photo first.")
            return
        self.confirm_defect_cb.setChecked(False)
        self._start_pipeline(full_run=True)

    def _get_current_ui_settings(self) -> Dict[str, Any]:
        bg_key = self.bg_combo.currentData()
        return {
            "photo_size": self.photo_size_combo.currentData(),
            "paper_size": self.paper_size_combo.currentData(),
            "copies": self.copies_spin.value(),
            "background": bg_key,
            "custom_bg_color": self.settings.get("custom_bg_color", "#FFFFFF"),
            "dpi": self.settings.get("dpi", 300),
            "gap_mm": self.settings.get("gap_mm", 2.0),
            "margin_mm": self.settings.get("margin_mm", 5.0),
            "min_printer_margin_mm": self.settings.get("min_printer_margin_mm", 3.0),
            "cut_lines": self.settings.get("cut_lines", True),
            "paper_orientation": self.settings.get("paper_orientation", "auto"),
            "head_ratio": self.settings.get("head_ratio", 0.75),
            "auto_enhance": self.auto_enhance_btn.isChecked(),
            "brightness": self.slider_bright.value(),
            "contrast": self.slider_contrast.value(),
            "warmth": self.slider_warmth.value(),
            "shadow_lift": self.slider_shadow.value(),
            "output_format": self.settings.get("output_format", "png"),
            "jpg_quality": self.settings.get("jpg_quality", 95),
            "save_outputs": self.settings.get("save_outputs", False),
            "calibration_scale_x": self.settings.get("calibration_scale_x", 1.0),
            "calibration_scale_y": self.settings.get("calibration_scale_y", 1.0),
            "calibration_offset_x_mm": self.settings.get("calibration_offset_x_mm", 0.0),
            "calibration_offset_y_mm": self.settings.get("calibration_offset_y_mm", 0.0),
        }

    def _start_pipeline(self, full_run: bool = True) -> None:
        # Race condition handling: if worker is currently running, remember newest settings and re-run
        if self.worker is not None and self.worker.isRunning():
            self._pending_pipeline_run = True
            if full_run:
                self._pending_full_run = True
            self.status_label.setText("Queued settings update...")
            return

        ui_settings = self._get_current_ui_settings()

        self._set_ui_busy(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10 if full_run else 40)

        is_reapply = not full_run and self.pipeline.has_cached_data()

        self.worker = PipelineWorker(
            self.pipeline,
            self.current_image,
            ui_settings,
            is_reapply=is_reapply,
            parent=self,
        )
        self.worker.progress_signal.connect(self._on_worker_progress)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.start()

    @Slot(str, int)
    def _on_worker_progress(self, step: str, pct: int) -> None:
        self.status_label.setText(step)
        self.status_bar.showMessage(step)
        self.progress_bar.setValue(pct)

    @Slot(object)
    def _on_worker_finished(self, result: Optional[PipelineResult]) -> None:
        self._set_ui_busy(False)
        self.progress_bar.setVisible(False)

        # Check if another run was requested while we were busy
        if self._pending_pipeline_run:
            next_full = self._pending_full_run
            self._pending_pipeline_run = False
            self._pending_full_run = False
            self._start_pipeline(full_run=next_full)
            return

        if not result or not result.final_photo:
            self.status_label.setText("Processing completed without output.")
            self._update_action_buttons_state()
            return

        self.latest_result = result
        self.adjust_crop_btn.setEnabled(self.pipeline.has_cached_data())

        # Update preview
        self.preview_panel.set_after_image(result.final_photo)
        if result.sheets:
            self.preview_panel.set_sheet_image(result.sheets[0])
            self.preview_panel.show_sheet()

        # Handle blocking issues and warnings
        self._evaluate_safety_banners(result)
        self._update_action_buttons_state()

        if result.has_blocking_issues:
            self.status_label.setText("⚠️ DEFECT DETECTED: Review blocking banner before printing.")
            self.status_bar.showMessage("Defects detected — Confirmation required")
        elif result.warnings:
            self.status_label.setText(f"Ready with note: {result.warnings[0]}")
            self.status_bar.showMessage("Done with warnings")
        else:
            self.status_label.setText(
                f"Ready! Created {result.num_sheets} sheet(s) ({self.copies_spin.value()} copies)."
            )
            self.status_bar.showMessage("Processing complete")

    @Slot(str)
    def _on_worker_error(self, err_msg: str) -> None:
        self._set_ui_busy(False)
        self.progress_bar.setVisible(False)

        # Check pending queue
        if self._pending_pipeline_run:
            next_full = self._pending_full_run
            self._pending_pipeline_run = False
            self._pending_full_run = False
            self._start_pipeline(full_run=next_full)
            return

        self.status_label.setText("Error during processing.")
        self.status_bar.showMessage("Processing failed")

        QMessageBox.warning(
            self,
            "Photo Processing Note",
            f"{err_msg}\n\n"
            f"Tip: If no face was detected, ensure the subject is centered and clearly lit.",
        )
        self._update_action_buttons_state()

    def _set_ui_busy(self, busy: bool) -> None:
        self.upload_btn.setEnabled(not busy)
        self._check_camera_setting()
        if busy:
            self.camera_btn.setEnabled(False)
        self.process_btn.setEnabled(not busy)
        self.adjust_crop_btn.setEnabled(not busy and self.pipeline.has_cached_data())
        if busy:
            self.print_btn.setEnabled(False)
            self.save_btn.setEnabled(False)

    def _evaluate_safety_banners(self, result: PipelineResult) -> None:
        """Display red blocking banner for defects or amber banner for warnings."""
        if result.has_blocking_issues:
            issues_text = " • " + "\n • ".join(result.blocking_issues)
            self.banner_label.setText(
                f"⛔ DEFECT DETECTED — PRINTING DISABLED FOR SAFETY:\n{issues_text}\n"
                f"Printing this photo may waste paper/money. To print anyway, check the confirmation below."
            )
            self.banner_frame.setVisible(True)
        else:
            self.banner_frame.setVisible(False)
            self.confirm_defect_cb.setChecked(False)

        if result.warnings and not result.has_blocking_issues:
            warn_text = " • " + "\n • ".join(result.warnings)
            self.warn_label.setText(f"⚠️ Notice:\n{warn_text}")
            self.warn_frame.setVisible(True)
        else:
            self.warn_frame.setVisible(False)

    def _on_defect_confirmation_toggled(self, checked: bool) -> None:
        self._update_action_buttons_state()

    def _is_result_stale(self) -> bool:
        """Check whether latest_result matches current UI values."""
        if not self.latest_result or not self.latest_result.settings_snapshot:
            return True
        snapshot = self.latest_result.settings_snapshot
        current = self._get_current_ui_settings()

        check_keys = [
            "photo_size", "paper_size", "copies", "background", "custom_bg_color",
            "brightness", "contrast", "warmth", "shadow_lift", "auto_enhance"
        ]
        for k in check_keys:
            if snapshot.get(k) != current.get(k):
                return True
        return False

    def _update_action_buttons_state(self) -> None:
        """Strictly control whether Print and Save buttons are enabled."""
        if self.latest_result is None or not self.latest_result.sheets:
            self.print_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            return

        # If result is stale versus current UI, disable buttons
        if self._is_result_stale():
            self.print_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.status_bar.showMessage("Settings changed — Re-applying...")
            return

        # If result has blocking issues, require explicit confirmation checkbox
        if self.latest_result.has_blocking_issues:
            can_proceed = self.confirm_defect_cb.isChecked()
            self.print_btn.setEnabled(can_proceed)
            self.save_btn.setEnabled(can_proceed)
        else:
            self.print_btn.setEnabled(True)
            self.save_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Interactive Crop Adjustment
    # -----------------------------------------------------------------------

    def _on_adjust_crop_clicked(self) -> None:
        if not self.pipeline.has_cached_data():
            QMessageBox.information(self, "Adjust Crop", "Process a photo first before adjusting crop.")
            return

        img = self.pipeline.cleaned_image or self.current_image
        if img is None:
            return

        # Calculate aspect ratio (width / height)
        size_key = self.photo_size_combo.currentData()
        w_mm, h_mm = PHOTO_SIZES.get(size_key, (35.0, 45.0))
        target_aspect = w_mm / h_mm

        # Determine current crop box
        current_crop = self.pipeline.manual_crop_box
        if current_crop is None and self.latest_result and self.latest_result.face_box:
            # Derive normalized crop box from face box and image size
            fb = self.latest_result.face_box
            from app.core.face_crop import calculate_crop_box
            box_px = calculate_crop_box(img.size, fb, target_aspect, head_ratio=0.75)
            iw, ih = img.size
            current_crop = (box_px[0] / iw, box_px[1] / ih, box_px[2] / iw, box_px[3] / ih)

        dlg = AdjustCropDialog(img, current_crop, target_aspect=target_aspect, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_crop = dlg.get_crop_box()
            self.pipeline.set_manual_crop(new_crop)
            # Re-run crop and layout
            self._start_pipeline(full_run=False)

    # -----------------------------------------------------------------------
    # Fast Tweaking Handlers
    # -----------------------------------------------------------------------

    def _on_slider_moved(self) -> None:
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._slider_timer.start()

    def _trigger_fast_reapply(self) -> None:
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_photo_size_changed(self) -> None:
        val = self.photo_size_combo.currentData()
        self.settings.set("photo_size", val)
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_paper_size_changed(self) -> None:
        val = self.paper_size_combo.currentData()
        self.settings.set("paper_size", val)
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_copies_changed(self) -> None:
        val = self.copies_spin.value()
        self.settings.set("copies", val)
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_auto_enhance_toggle(self) -> None:
        checked = self.auto_enhance_btn.isChecked()
        self.auto_enhance_btn.setText(f"✨ Auto Enhance: {'ON' if checked else 'OFF'}")
        self.settings.set("auto_enhance", checked)
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _reset_lighting_sliders(self) -> None:
        self.slider_bright.setValue(0)
        self.slider_contrast.setValue(0)
        self.slider_warmth.setValue(0)
        self.slider_shadow.setValue(0)
        self.auto_enhance_btn.setChecked(False)
        self.auto_enhance_btn.setText("✨ Auto Enhance: OFF")
        self.settings.set("auto_enhance", False)
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_bg_changed(self) -> None:
        val = self.bg_combo.currentData()
        self.settings.set("background", val)
        self._update_color_preview()
        self._update_action_buttons_state()
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_pick_custom_color(self) -> None:
        current = self.settings.get("custom_bg_color", "#FFFFFF")
        color = QColorDialog.getColor(QColor(current), self, "Select Custom Background Color")
        if color.isValid():
            self.settings.set("custom_bg_color", color.name())
            # Select custom in combo if not selected
            for i in range(self.bg_combo.count()):
                if self.bg_combo.itemData(i) == "custom":
                    self.bg_combo.setCurrentIndex(i)
                    break
            self._update_color_preview()
            self._update_action_buttons_state()
            if self.pipeline.has_cached_data():
                self._start_pipeline(full_run=False)

    def _update_color_preview(self) -> None:
        key = self.bg_combo.currentData()
        if key == "custom":
            hex_c = self.settings.get("custom_bg_color", "#FFFFFF")
            self.custom_color_btn.setEnabled(True)
        else:
            hex_c = background_hex(key) if key else "#FFFFFF"
            self.custom_color_btn.setEnabled(False)
        from app.ui.theme import detect_scheme
        border_c = "#3E4D64" if detect_scheme() else "#CBD5E1"
        self.color_preview.setStyleSheet(
            f"background-color: {hex_c}; border: 1.5px solid {border_c}; border-radius: 6px;"
        )

    def _on_preset_selected(self) -> None:
        preset = self.preset_combo.currentData()
        if not preset:
            return

        # Block signals so only ONE pipeline run is triggered
        self.photo_size_combo.blockSignals(True)
        self.paper_size_combo.blockSignals(True)
        self.copies_spin.blockSignals(True)
        self.bg_combo.blockSignals(True)

        try:
            if "photo_size" in preset:
                for i in range(self.photo_size_combo.count()):
                    if self.photo_size_combo.itemData(i) == preset["photo_size"]:
                        self.photo_size_combo.setCurrentIndex(i)
                        self.settings.set("photo_size", preset["photo_size"])
                        break

            if "paper_size" in preset:
                for i in range(self.paper_size_combo.count()):
                    if self.paper_size_combo.itemData(i) == preset["paper_size"]:
                        self.paper_size_combo.setCurrentIndex(i)
                        self.settings.set("paper_size", preset["paper_size"])
                        break

            if "copies" in preset:
                self.copies_spin.setValue(preset["copies"])
                self.settings.set("copies", preset["copies"])

            if "background" in preset:
                for i in range(self.bg_combo.count()):
                    if self.bg_combo.itemData(i) == preset["background"]:
                        self.bg_combo.setCurrentIndex(i)
                        self.settings.set("background", preset["background"])
                        break
        finally:
            self.photo_size_combo.blockSignals(False)
            self.paper_size_combo.blockSignals(False)
            self.copies_spin.blockSignals(False)
            self.bg_combo.blockSignals(False)

        self._update_color_preview()
        self.status_bar.showMessage(f"Applied preset: {preset.get('name')}", 3000)

        # Re-apply once
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    # -----------------------------------------------------------------------
    # Printing & Saving (Explicit Customer Operations & Privacy)
    # -----------------------------------------------------------------------

    def _record_output_privacy_save(self) -> None:
        """Save copies only on explicit Save/Print with timestamp and cleanup old files."""
        if not self.latest_result or not self.latest_result.sheets:
            return
        try:
            from app.core.layout import save_sheet
            out_dir = user_output_dir()
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fmt = self.settings.get("output_format", "png")
            dpi = self.settings.get("dpi", 300)
            copies = self.copies_spin.value()

            # Save sheets
            for idx, sheet in enumerate(self.latest_result.sheets):
                s_path = out_dir / f"passport_{ts}_{copies}copies_sheet{idx+1}.{fmt}"
                save_sheet(sheet, s_path, fmt, dpi)

            # Cleanup older files per policy
            cleanup_old_saved_files(keep_days=self.settings.get("keep_saved_days", 0))
        except Exception as exc:
            logger.warning("Privacy output record failed: %s", exc)

    def _on_print_clicked(self) -> None:
        if not self.latest_result or not self.latest_result.sheets:
            QMessageBox.information(self, "Print", "No sheets available to print.")
            return

        if self.latest_result.has_blocking_issues and not self.confirm_defect_cb.isChecked():
            QMessageBox.warning(
                self,
                "Print Blocked",
                "This photo has defects that may cause print rejection.\n"
                "Please verify the defects and check the confirmation box to print anyway.",
            )
            return

        printer_name = self.settings.get("printer_name", "").strip() or None
        dpi = self.settings.get("dpi", 300)

        confirm = QMessageBox.question(
            self,
            "Confirm Print",
            f"Print {len(self.latest_result.sheets)} sheet(s) to:\n"
            f"{printer_name or 'Default Printer'}?\n\n"
            f"Photos will be printed at 100% exact physical size.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.status_label.setText("Sending job to printer...")
        self.status_bar.showMessage("Printing...")

        try:
            from app.printing.printer import print_sheets
            cal_scale = (
                self.settings.get("calibration_scale_x", 1.0),
                self.settings.get("calibration_scale_y", 1.0),
            )
            cal_offset = (
                self.settings.get("calibration_offset_x_mm", 0.0),
                self.settings.get("calibration_offset_y_mm", 0.0),
            )
            print_sheets(
                self.latest_result.sheets,
                printer_name=printer_name,
                dpi=dpi,
                calibration_scale=cal_scale,
                calibration_offset_mm=cal_offset,
            )
            # Record output copy for shopkeeper records per retention policy
            self._record_output_privacy_save()

            QMessageBox.information(self, "Print Sent", "Print job sent successfully to printer!")
            self.status_label.setText("Printed successfully.")
            self.status_bar.showMessage("Print complete")
        except Exception as exc:
            logger.error("Printing failed: %s", exc)
            QMessageBox.warning(
                self,
                "Printing Problem",
                f"{exc}\n\n"
                f"You can also use 'Save Sheet (PDF / PNG)' to save and print using Windows Photo Viewer or Acrobat.",
            )
            self.status_label.setText("Printing error.")

    def _on_save_sheet_clicked(self) -> None:
        if not self.latest_result or not self.latest_result.sheets:
            QMessageBox.information(self, "Save Sheet", "No sheet available to save.")
            return

        if self.latest_result.has_blocking_issues and not self.confirm_defect_cb.isChecked():
            QMessageBox.warning(
                self,
                "Save Blocked",
                "This photo has defects that may cause rejection.\n"
                "Please verify the defects and check the confirmation box to save anyway.",
            )
            return

        file_filter = "PDF Document (*.pdf);;PNG Image (*.png);;JPEG Image (*.jpg)"
        dest, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Print Sheet",
            f"Passport_Photos_{self.copies_spin.value()}_Copies",
            file_filter,
        )
        if not dest:
            return

        dest_path = Path(dest)
        dpi = self.settings.get("dpi", 300)

        try:
            if "pdf" in selected_filter.lower() or dest_path.suffix.lower() == ".pdf":
                from app.printing.printer import save_as_pdf
                save_as_pdf(self.latest_result.sheets, dest_path, dpi=dpi)
            else:
                from app.core.layout import save_sheet
                fmt = "jpg" if ("jpg" in selected_filter.lower() or dest_path.suffix.lower() in [".jpg", ".jpeg"]) else "png"
                if len(self.latest_result.sheets) == 1:
                    save_sheet(self.latest_result.sheets[0], dest_path, fmt=fmt, dpi=dpi)
                else:
                    for i, s in enumerate(self.latest_result.sheets):
                        s_name = dest_path.with_name(f"{dest_path.stem}_{i+1}{dest_path.suffix}")
                        save_sheet(s, s_name, fmt=fmt, dpi=dpi)

            # Record privacy output save
            self._record_output_privacy_save()

            QMessageBox.information(self, "Saved", f"Sheet(s) saved successfully:\n{dest_path}")
            self.status_label.setText("Sheet saved.")
        except Exception as exc:
            logger.error("Failed to save sheets: %s", exc)
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{exc}")

    def _print_calibration_sheet(self) -> None:
        """Generate and print or save printer calibration sheet."""
        paper = self.paper_size_combo.currentData() or "4x6"
        dpi = self.settings.get("dpi", 300)

        choice = QMessageBox.question(
            self,
            "Print Calibration Sheet",
            f"Generate 50mm ruler calibration sheet for paper size '{paper}'?\n\n"
            f"Click Yes to send directly to printer, or No to save as PDF/PNG.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return

        try:
            from app.printing.printer import generate_calibration_sheet, print_sheet, save_as_pdf
            cal_sheet = generate_calibration_sheet(paper_size=paper, dpi=dpi)

            if choice == QMessageBox.StandardButton.Yes:
                printer_name = self.settings.get("printer_name", "").strip() or None
                print_sheet(cal_sheet, printer_name=printer_name, dpi=dpi)
                QMessageBox.information(
                    self,
                    "Calibration Sheet Sent",
                    "Calibration sheet sent to printer!\n"
                    "Measure the 50mm ruler with a scale to verify 100% physical accuracy.",
                )
            else:
                dest, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Calibration Sheet",
                    f"Printer_Calibration_{paper}",
                    "PDF Document (*.pdf);;PNG Image (*.png)",
                )
                if dest:
                    dest_p = Path(dest)
                    if dest_p.suffix.lower() == ".pdf":
                        save_as_pdf([cal_sheet], dest_p, dpi=dpi)
                    else:
                        from app.core.layout import save_sheet
                        save_sheet(cal_sheet, dest_p, fmt="png", dpi=dpi)
                    QMessageBox.information(self, "Saved", f"Calibration sheet saved to:\n{dest_p}")
        except Exception as exc:
            logger.error("Calibration sheet error: %s", exc)
            QMessageBox.warning(self, "Calibration Error", f"Could not generate calibration sheet:\n{exc}")

    # -----------------------------------------------------------------------
    # Setup Wizard / Settings Reopen
    # -----------------------------------------------------------------------

    def _open_settings_wizard(self) -> None:
        wizard = SetupWizard(self.settings, self)
        wizard.settings_saved.connect(self._on_settings_reloaded)
        wizard.exec()

    def _on_settings_reloaded(self) -> None:
        self._load_settings_into_ui()
        self._check_camera_setting()
        shop_title = self.settings.get("shop_name", "").strip()
        if shop_title:
            self.setWindowTitle(f"Passport Photo App — {shop_title}")
        self.status_bar.showMessage("Settings updated.")
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Passport Photo App",
            f"<h3>Passport Photo App</h3>"
            f"<p><b>Version:</b> {self.settings.get('app_version', '1.0.0')}</p>"
            f"<p>Built for CSC (Common Service Centre) and Digital Seva Kendra operators in India.</p>"
            f"<p>Features:</p>"
            f"<ul>"
            f"<li>100% Offline AI Background Removal</li>"
            f"<li>Automatic Face Centering & Passport Proportions</li>"
            f"<li>Multi-copy Photo Sheet Arrangement (4x6, 5x7, A4)</li>"
            f"<li>Exact 100% Physical Size Windows Printing</li>"
            f"<li>Quality Safety Banners & Defect Confirmation</li>"
            f"<li>Interactive Fine-Tuning Crop Tool</li>"
            f"</ul>"
            f"<p>© 2026 Passport Photo App</p>",
        )
