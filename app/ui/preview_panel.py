"""Reusable image preview widget.

Shows a PIL/QImage with zoom-to-fit, before/after toggle,
and sheet grid preview. Handles high-DPI scaling efficiently.
Keeps photos completely untinted and true-to-color.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy,
)

from PIL import Image

logger = logging.getLogger(__name__)


def pil_to_qimage(pil_img: Image.Image) -> QImage:
    """Convert a PIL Image to QImage efficiently."""
    if pil_img.mode == "RGBA":
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    elif pil_img.mode == "RGB":
        data = pil_img.tobytes("raw", "RGB")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGB888)
    else:
        converted = pil_img.convert("RGB")
        data = converted.tobytes("raw", "RGB")
        qimg = QImage(data, converted.width, converted.height, QImage.Format.Format_RGB888)
    return qimg.copy()


def pil_to_qpixmap(pil_img: Image.Image, max_size: int = 2000) -> QPixmap:
    """Convert PIL Image to QPixmap, downscaling if needed for display."""
    w, h = pil_img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        pil_img = pil_img.resize(new_size, Image.LANCZOS)
    return QPixmap.fromImage(pil_to_qimage(pil_img))


class PreviewPanel(QWidget):
    """Image preview widget with zoom-to-fit and before/after toggle.

    Signals:
        image_clicked: Emitted when the image is clicked.
    """

    image_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._before_pixmap: Optional[QPixmap] = None
        self._after_pixmap: Optional[QPixmap] = None
        self._sheet_pixmap: Optional[QPixmap] = None
        self._showing_before = False
        self._showing_sheet = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Image display area
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_label.setMinimumSize(250, 250)
        self._image_label.setObjectName("previewPlaceholder")
        self._image_label.setText("Drop a photo here or click Upload")
        layout.addWidget(self._image_label, stretch=1)

        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._before_after_btn = QPushButton("Before / After")
        self._before_after_btn.setFixedHeight(36)
        self._before_after_btn.setCheckable(True)
        self._before_after_btn.clicked.connect(self._toggle_before_after)
        self._before_after_btn.setEnabled(False)
        btn_layout.addWidget(self._before_after_btn)

        self._sheet_btn = QPushButton("Sheet Preview")
        self._sheet_btn.setFixedHeight(36)
        self._sheet_btn.setCheckable(True)
        self._sheet_btn.clicked.connect(self._toggle_sheet)
        self._sheet_btn.setEnabled(False)
        btn_layout.addWidget(self._sheet_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_before_image(self, pil_img: Image.Image) -> None:
        """Set the 'before' (original) image."""
        self._before_pixmap = pil_to_qpixmap(pil_img)
        self._before_after_btn.setEnabled(self._after_pixmap is not None)
        if self._after_pixmap is None:
            self._show_pixmap(self._before_pixmap)

    def set_after_image(self, pil_img: Image.Image) -> None:
        """Set the 'after' (processed) image."""
        self._after_pixmap = pil_to_qpixmap(pil_img)
        self._before_after_btn.setEnabled(self._before_pixmap is not None)
        self._showing_before = False
        self._before_after_btn.setChecked(False)
        self._showing_sheet = False
        self._sheet_btn.setChecked(False)
        self._show_pixmap(self._after_pixmap)

    def set_sheet_image(self, pil_img: Image.Image) -> None:
        """Set the sheet preview image."""
        self._sheet_pixmap = pil_to_qpixmap(pil_img, max_size=3000)
        self._sheet_btn.setEnabled(True)

    def show_sheet(self) -> None:
        """Switch view directly to sheet preview."""
        if self._sheet_pixmap:
            self._showing_sheet = True
            self._sheet_btn.setChecked(True)
            self._showing_before = False
            self._before_after_btn.setChecked(False)
            self._show_pixmap(self._sheet_pixmap)

    def clear(self) -> None:
        """Clear all images."""
        self._before_pixmap = None
        self._after_pixmap = None
        self._sheet_pixmap = None
        self._showing_before = False
        self._showing_sheet = False
        self._before_after_btn.setEnabled(False)
        self._before_after_btn.setChecked(False)
        self._sheet_btn.setEnabled(False)
        self._sheet_btn.setChecked(False)
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText("Drop a photo here or click Upload")

    def _show_pixmap(self, pixmap: QPixmap) -> None:
        """Display a pixmap scaled to fit the label without any color tinting."""
        if pixmap is None or pixmap.isNull():
            return
        self._image_label.setText("")
        label_size = self._image_label.size()
        scaled = pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    def _toggle_before_after(self, checked: bool) -> None:
        """Toggle between before and after images."""
        self._showing_sheet = False
        self._sheet_btn.setChecked(False)

        if checked and self._before_pixmap:
            self._showing_before = True
            self._show_pixmap(self._before_pixmap)
        elif self._after_pixmap:
            self._showing_before = False
            self._show_pixmap(self._after_pixmap)

    def _toggle_sheet(self, checked: bool) -> None:
        """Toggle sheet preview."""
        self._showing_before = False
        self._before_after_btn.setChecked(False)

        if checked and self._sheet_pixmap:
            self._showing_sheet = True
            self._show_pixmap(self._sheet_pixmap)
        elif self._after_pixmap:
            self._showing_sheet = False
            self._show_pixmap(self._after_pixmap)

    def resizeEvent(self, event) -> None:
        """Re-scale the image when the widget is resized."""
        super().resizeEvent(event)
        if self._showing_sheet and self._sheet_pixmap:
            self._show_pixmap(self._sheet_pixmap)
        elif self._showing_before and self._before_pixmap:
            self._show_pixmap(self._before_pixmap)
        elif self._after_pixmap:
            self._show_pixmap(self._after_pixmap)
        elif self._before_pixmap:
            self._show_pixmap(self._before_pixmap)

    def mousePressEvent(self, event) -> None:
        """Emit signal when image is clicked."""
        super().mousePressEvent(event)
        self.image_clicked.emit()
