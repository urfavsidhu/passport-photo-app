"""Main application window for Passport Photo App.

Provides the primary interface for daily CSC shop operations:
- 1-click automatic workflow upon upload/camera capture
- Big buttons, clear high-contrast controls
- Non-blocking asynchronous processing with QThread
- Fast slider tweaking using cached AI cutouts
- Direct physical-size printing and multi-format sheet export
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMenuBar,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox,
    QStatusBar, QVBoxLayout, QWidget,
)
from PIL import Image

from app.core.pipeline import PassportPipeline, PipelineResult
from app.settings_manager import (
    BACKGROUND_COLORS, PAPER_SIZES, PHOTO_SIZES, SettingsManager,
    background_hex, resource_path, user_data_dir,
)
from app.ui.preview_panel import PreviewPanel
from app.ui.setup_wizard import SetupWizard

logger = logging.getLogger(__name__)


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
        self.preview_label.setStyleSheet("background-color: #0F172A; color: white; border-radius: 8px;")
        self.preview_label.setMinimumSize(600, 400)
        layout.addWidget(self.preview_label, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.capture_btn = QPushButton("📷 Capture Photo")
        self.capture_btn.setFixedHeight(48)
        self.capture_btn.setStyleSheet("background-color: #16A34A; color: white; font-size: 16px; font-weight: bold;")
        self.capture_btn.clicked.connect(self._on_capture)
        btn_layout.addWidget(self.capture_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(48)
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

        # Debounce timer for slider adjustments
        self._slider_timer = QTimer(self)
        self._slider_timer.setSingleShot(True)
        self._slider_timer.setInterval(300)
        self._slider_timer.timeout.connect(self._trigger_fast_reapply)

        self._init_window()
        self._create_menu()
        self._setup_ui()
        self._load_settings_into_ui()

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

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        settings_menu = menubar.addMenu("&Settings")
        setup_action = QAction("&Configuration Wizard...", self)
        setup_action.triggered.connect(self._open_settings_wizard)
        settings_menu.addAction(setup_action)

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

        # Left Column: Image Preview & Before/After
        left_box = QVBoxLayout()
        left_box.setSpacing(12)

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
        scroll.setMinimumWidth(380)

        right_widget = QWidget()
        right_box = QVBoxLayout(right_widget)
        right_box.setContentsMargins(8, 0, 8, 8)
        right_box.setSpacing(16)

        # Preset Selector
        preset_group = QGroupBox("📋 Quick Document Presets")
        preset_layout = QHBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Select standard size...", None)
        for p in self.settings.load_presets():
            self.preset_combo.addItem(p["name"], p)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.preset_combo)
        right_box.addWidget(preset_group)

        # Background Group
        bg_group = QGroupBox("🎨 Background Color")
        bg_layout = QGridLayout(bg_group)
        bg_layout.setSpacing(10)

        bg_layout.addWidget(QLabel("Color:"), 0, 0)
        self.bg_combo = QComboBox()
        for k, v in BACKGROUND_COLORS.items():
            if k == "custom":
                self.bg_combo.addItem("Custom Color...", k)
            else:
                self.bg_combo.addItem(f"{k.replace('_', ' ').title()}", k)
        self.bg_combo.currentIndexChanged.connect(self._on_bg_changed)
        bg_layout.addWidget(self.bg_combo, 0, 1)

        self.custom_color_btn = QPushButton("Pick Color")
        self.custom_color_btn.setFixedHeight(36)
        self.custom_color_btn.clicked.connect(self._on_pick_custom_color)
        bg_layout.addWidget(self.custom_color_btn, 1, 0)

        self.color_preview = QFrame()
        self.color_preview.setObjectName("colorPreview")
        self.color_preview.setFixedSize(50, 36)
        bg_layout.addWidget(self.color_preview, 1, 1)

        right_box.addWidget(bg_group)

        # Photo & Print Layout Group
        size_group = QGroupBox("📐 Photo Size & Print Copies")
        size_layout = QGridLayout(size_group)
        size_layout.setSpacing(10)

        size_layout.addWidget(QLabel("Photo Size:"), 0, 0)
        self.photo_size_combo = QComboBox()
        for k, (w, h) in PHOTO_SIZES.items():
            self.photo_size_combo.addItem(f"{k} mm ({w:.0f}x{h:.0f})", k)
        self.photo_size_combo.currentIndexChanged.connect(self._on_setting_changed)
        size_layout.addWidget(self.photo_size_combo, 0, 1)

        size_layout.addWidget(QLabel("Paper Size:"), 1, 0)
        self.paper_size_combo = QComboBox()
        for k, (w, h) in PAPER_SIZES.items():
            self.paper_size_combo.addItem(f"{k} ({w:.0f}x{h:.0f} mm)", k)
        self.paper_size_combo.currentIndexChanged.connect(self._on_setting_changed)
        size_layout.addWidget(self.paper_size_combo, 1, 1)

        size_layout.addWidget(QLabel("Number of Copies:"), 2, 0)
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 100)
        self.copies_spin.setValue(self.settings.get("copies", 8))
        self.copies_spin.valueChanged.connect(self._on_setting_changed)
        size_layout.addWidget(self.copies_spin, 2, 1)

        right_box.addWidget(size_group)

        # Lighting Adjustments Group
        light_group = QGroupBox("💡 Lighting & Touch-up")
        light_layout = QVBoxLayout(light_group)
        light_layout.setSpacing(8)

        self.auto_enhance_btn = QPushButton("✨ Auto Enhance: ON")
        self.auto_enhance_btn.setCheckable(True)
        self.auto_enhance_btn.setChecked(self.settings.get("auto_enhance", True))
        self.auto_enhance_btn.clicked.connect(self._on_auto_enhance_toggle)
        light_layout.addWidget(self.auto_enhance_btn)

        self.slider_bright = self._create_slider("Brightness", -100, 100, self.settings.get("brightness", 0), light_layout)
        self.slider_contrast = self._create_slider("Contrast", -100, 100, self.settings.get("contrast", 0), light_layout)
        self.slider_warmth = self._create_slider("Warmth (Color Temp)", -100, 100, self.settings.get("warmth", 0), light_layout)
        self.slider_shadow = self._create_slider("Shadow Lift", 0, 100, self.settings.get("shadow_lift", 0), light_layout)

        reset_btn = QPushButton("↺ Reset Sliders")
        reset_btn.setFixedHeight(34)
        reset_btn.setStyleSheet("background-color: #E2E8F0; color: #334155;")
        reset_btn.clicked.connect(self._reset_lighting_sliders)
        light_layout.addWidget(reset_btn)

        right_box.addWidget(light_group)

        # Primary Action Buttons
        act_box = QVBoxLayout()
        act_box.setSpacing(12)

        self.process_btn = QPushButton("⚡ Process Photo")
        self.process_btn.setObjectName("processBtn")
        self.process_btn.clicked.connect(self._on_process_clicked)
        act_box.addWidget(self.process_btn)

        self.print_btn = QPushButton("🖨️ Print Sheets")
        self.print_btn.setObjectName("printBtn")
        self.print_btn.clicked.connect(self._on_print_clicked)
        self.print_btn.setEnabled(False)
        act_box.addWidget(self.print_btn)

        self.save_btn = QPushButton("💾 Save Sheet (PDF / PNG)")
        self.save_btn.setObjectName("saveBtn")
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
        ae = self.settings.get("auto_enhance", True)
        self.auto_enhance_btn.setChecked(ae)
        self.auto_enhance_btn.setText(f"✨ Auto Enhance: {'ON' if ae else 'OFF'}")

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
            cam_idx = 0
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
            # Automatically process photo immediately (One-Click Shopkeeper experience)
            self._start_pipeline(full_run=True)
        except Exception as exc:
            logger.error("Failed to load image %s: %s", path, exc)
            QMessageBox.critical(self, "Image Load Error", f"Could not open image:\n{exc}")

    # -----------------------------------------------------------------------
    # Pipeline Execution
    # -----------------------------------------------------------------------

    def _on_process_clicked(self) -> None:
        if self.current_image is None:
            QMessageBox.information(self, "No Photo", "Please upload or capture a photo first.")
            return
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
            "save_outputs": self.settings.get("save_outputs", True),
        }

    def _start_pipeline(self, full_run: bool = True) -> None:
        if self.worker is not None and self.worker.isRunning():
            logger.debug("Worker already running, skipping trigger.")
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

        if not result or not result.final_photo:
            self.status_label.setText("Processing completed without output.")
            return

        self.latest_result = result

        # Update preview
        self.preview_panel.set_after_image(result.final_photo)
        if result.sheets:
            self.preview_panel.set_sheet_image(result.sheets[0])
            self.preview_panel.show_sheet()

        self.print_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        # Notify warnings if any
        if result.warnings:
            msg = "\n".join(result.warnings)
            self.status_label.setText(f"Ready with note: {result.warnings[0]}")
            self.status_bar.showMessage("Done with warnings")
        else:
            self.status_label.setText(f"Ready! Created {result.num_sheets} sheet(s) ({self.copies_spin.value()} copies).")
            self.status_bar.showMessage("Processing complete")

        # Auto save if configured
        if self.settings.get("save_outputs", True):
            self._auto_save_result(result)

    @Slot(str)
    def _on_worker_error(self, err_msg: str) -> None:
        self._set_ui_busy(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error during processing.")
        self.status_bar.showMessage("Processing failed")

        QMessageBox.warning(
            self,
            "Photo Processing Note",
            f"{err_msg}\n\n"
            f"Tip: If no face was detected, ensure the subject is centered and clearly lit.",
        )

    def _set_ui_busy(self, busy: bool) -> None:
        self.upload_btn.setEnabled(not busy)
        self.camera_btn.setEnabled(not busy)
        self.process_btn.setEnabled(not busy)
        if busy:
            self.print_btn.setEnabled(False)
            self.save_btn.setEnabled(False)

    def _auto_save_result(self, result: PipelineResult) -> None:
        try:
            from app.core.layout import save_sheet
            out_dir = resource_path("data/output")
            out_dir.mkdir(parents=True, exist_ok=True)

            fmt = self.settings.get("output_format", "png")
            dpi = self.settings.get("dpi", 300)

            # Save passport photo
            if result.final_photo:
                p_path = out_dir / f"passport_photo.{fmt}"
                result.final_photo.save(str(p_path), dpi=(dpi, dpi))

            # Save sheet(s)
            for idx, sheet in enumerate(result.sheets):
                s_path = out_dir / f"sheet_{idx + 1}.{fmt}"
                save_sheet(sheet, s_path, fmt, dpi)
            logger.info("Auto-saved outputs to %s", out_dir)
        except Exception as exc:
            logger.warning("Auto-save failed: %s", exc)

    # -----------------------------------------------------------------------
    # Fast Tweaking Handlers
    # -----------------------------------------------------------------------

    def _on_slider_moved(self) -> None:
        if self.pipeline.has_cached_data():
            self._slider_timer.start()

    def _trigger_fast_reapply(self) -> None:
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_setting_changed(self) -> None:
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_auto_enhance_toggle(self) -> None:
        checked = self.auto_enhance_btn.isChecked()
        self.auto_enhance_btn.setText(f"✨ Auto Enhance: {'ON' if checked else 'OFF'}")
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _reset_lighting_sliders(self) -> None:
        self.slider_bright.setValue(0)
        self.slider_contrast.setValue(0)
        self.slider_warmth.setValue(0)
        self.slider_shadow.setValue(0)
        self.auto_enhance_btn.setChecked(True)
        self.auto_enhance_btn.setText("✨ Auto Enhance: ON")
        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    def _on_bg_changed(self) -> None:
        self._update_color_preview()
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
        self.color_preview.setStyleSheet(
            f"background-color: {hex_c}; border: 2px solid #CBD5E1; border-radius: 6px;"
        )

    def _on_preset_selected(self) -> None:
        preset = self.preset_combo.currentData()
        if not preset:
            return

        if "photo_size" in preset:
            for i in range(self.photo_size_combo.count()):
                if self.photo_size_combo.itemData(i) == preset["photo_size"]:
                    self.photo_size_combo.setCurrentIndex(i)
                    break

        if "paper_size" in preset:
            for i in range(self.paper_size_combo.count()):
                if self.paper_size_combo.itemData(i) == preset["paper_size"]:
                    self.paper_size_combo.setCurrentIndex(i)
                    break

        if "copies" in preset:
            self.copies_spin.setValue(preset["copies"])

        if "background" in preset:
            for i in range(self.bg_combo.count()):
                if self.bg_combo.itemData(i) == preset["background"]:
                    self.bg_combo.setCurrentIndex(i)
                    break
            self._update_color_preview()

        self.status_bar.showMessage(f"Applied preset: {preset.get('name')}", 3000)

        if self.pipeline.has_cached_data():
            self._start_pipeline(full_run=False)

    # -----------------------------------------------------------------------
    # Printing & Saving
    # -----------------------------------------------------------------------

    def _on_print_clicked(self) -> None:
        if not self.latest_result or not self.latest_result.sheets:
            QMessageBox.information(self, "Print", "No sheets available to print.")
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
            print_sheets(self.latest_result.sheets, printer_name=printer_name, dpi=dpi)
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

            QMessageBox.information(self, "Saved", f"Sheet(s) saved successfully:\n{dest_path}")
            self.status_label.setText("Sheet saved.")
        except Exception as exc:
            logger.error("Failed to save sheets: %s", exc)
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{exc}")

    # -----------------------------------------------------------------------
    # Setup Wizard / Settings Reopen
    # -----------------------------------------------------------------------

    def _open_settings_wizard(self) -> None:
        wizard = SetupWizard(self.settings, self)
        wizard.settings_saved.connect(self._on_settings_reloaded)
        wizard.exec()

    def _on_settings_reloaded(self) -> None:
        self._load_settings_into_ui()
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
            f"</ul>"
            f"<p>© 2026 Passport Photo App</p>",
        )
