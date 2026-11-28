"""Interactive crop adjustment dialog.

Allows the operator to drag, zoom, and reposition the crop box on the
photo with visible head/chin guidelines to fix automatic framing errors.
"""

import logging
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QWidget, QSizePolicy
)
from PIL import Image

from app.ui.preview_panel import pil_to_qpixmap

logger = logging.getLogger(__name__)


class CropOverlayWidget(QWidget):
    """Widget that renders the photo and an interactive draggable crop rectangle."""

    crop_changed = Signal(QRectF)

    def __init__(self, pil_image: Image.Image, aspect_ratio: float, head_ratio: float = 0.75, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pil_image = pil_image
        self.aspect_ratio = aspect_ratio  # width / height
        self.head_ratio = head_ratio
        self.pixmap = pil_to_qpixmap(pil_image)

        self._img_rect = QRectF()
        self._crop_norm = QRectF(0.2, 0.1, 0.6, 0.6 / aspect_ratio if aspect_ratio > 0 else 0.6)  # normalized (0..1)
        self._ensure_aspect()

        self._dragging = False
        self._resizing = False
        self._last_mouse_pos = QPointF()
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 400)

    def set_crop_box_pixels(self, x: int, y: int, w: int, h: int) -> None:
        """Set crop box from image pixel coordinates."""
        iw, ih = self.pil_image.size
        self._crop_norm = QRectF(x / iw, y / ih, w / iw, h / ih)
        self._ensure_aspect()
        self.update()

    def get_crop_box_pixels(self) -> Tuple[int, int, int, int]:
        """Return (x, y, w, h) in original image pixel coordinates."""
        iw, ih = self.pil_image.size
        cx = int(round(self._crop_norm.x() * iw))
        cy = int(round(self._crop_norm.y() * ih))
        cw = int(round(self._crop_norm.width() * iw))
        ch = int(round(self._crop_norm.height() * ih))
        # Clamp to image boundaries
        cx = max(0, min(iw - 10, cx))
        cy = max(0, min(ih - 10, cy))
        cw = max(10, min(iw - cx, cw))
        ch = max(10, min(ih - cy, ch))
        return (cx, cy, cw, ch)

    def set_zoom(self, scale_factor: float) -> None:
        """Scale crop box around its center."""
        center = self._crop_norm.center()
        new_w = max(0.1, min(1.0, scale_factor))
        new_h = new_w / self.aspect_ratio if self.aspect_ratio > 0 else new_w
        if new_h > 1.0:
            new_h = 1.0
            new_w = new_h * self.aspect_ratio

        self._crop_norm = QRectF(center.x() - new_w / 2, center.y() - new_h / 2, new_w, new_h)
        self._clamp_crop()
        self.update()

    def _ensure_aspect(self) -> None:
        """Ensure normalized crop rectangle matches target aspect ratio."""
        iw, ih = self.pil_image.size
        pixel_aspect = (self._crop_norm.width() * iw) / (self._crop_norm.height() * ih)
        if abs(pixel_aspect - self.aspect_ratio) > 0.001 and self.aspect_ratio > 0:
            # Adjust height in normalized coords
            norm_h = (self._crop_norm.width() * iw / self.aspect_ratio) / ih
            self._crop_norm.setHeight(norm_h)
        self._clamp_crop()

    def _clamp_crop(self) -> None:
        """Keep crop box inside [0, 0, 1, 1]."""
        w = min(1.0, self._crop_norm.width())
        h = min(1.0, self._crop_norm.height())
        x = max(0.0, min(1.0 - w, self._crop_norm.x()))
        y = max(0.0, min(1.0 - h, self._crop_norm.y()))
        self._crop_norm = QRectF(x, y, w, h)

    def _crop_screen_rect(self) -> QRectF:
        """Convert normalized crop to widget screen coordinates."""
        return QRectF(
            self._img_rect.x() + self._crop_norm.x() * self._img_rect.width(),
            self._img_rect.y() + self._crop_norm.y() * self._img_rect.height(),
            self._crop_norm.width() * self._img_rect.width(),
            self._crop_norm.height() * self._img_rect.height(),
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Calculate image draw rect
        avail_w, avail_h = self.width(), self.height()
        pix_w, pix_h = self.pixmap.width(), self.pixmap.height()
        scale = min(avail_w / pix_w, avail_h / pix_h)
        draw_w = pix_w * scale
        draw_h = pix_h * scale
        draw_x = (avail_w - draw_w) / 2
        draw_y = (avail_h - draw_h) / 2
        self._img_rect = QRectF(draw_x, draw_y, draw_w, draw_h)

        # Draw scaled background photo
        painter.drawPixmap(self._img_rect.toRect(), self.pixmap)

        # 2. Semi-transparent dark overlay outside crop box
        crop_s = self._crop_screen_rect()
        overlay = QColor(0, 0, 0, 140)
        # Top, bottom, left, right dark rectangles
        painter.fillRect(QRectF(self._img_rect.left(), self._img_rect.top(), self._img_rect.width(), max(0.0, crop_s.top() - self._img_rect.top())), overlay)
        painter.fillRect(QRectF(self._img_rect.left(), crop_s.bottom(), self._img_rect.width(), max(0.0, self._img_rect.bottom() - crop_s.bottom())), overlay)
        painter.fillRect(QRectF(self._img_rect.left(), crop_s.top(), max(0.0, crop_s.left() - self._img_rect.left()), crop_s.height()), overlay)
        painter.fillRect(QRectF(crop_s.right(), crop_s.top(), max(0.0, self._img_rect.right() - crop_s.right()), crop_s.height()), overlay)

        # 3. Main crop box border
        pen = QPen(QColor("#2E7D32"), 2)
        painter.setPen(pen)
        painter.drawRect(crop_s)

        # 4. Head Guidelines
        # Top of hair guideline (~10% from crop top for 0.75 head ratio)
        top_hair_y = crop_s.top() + crop_s.height() * (1.0 - self.head_ratio) * 0.3
        # Chin guideline
        chin_y = top_hair_y + crop_s.height() * self.head_ratio

        guide_pen = QPen(QColor("#FFD54F"), 1, Qt.PenStyle.DashLine)
        painter.setPen(guide_pen)
        painter.drawLine(QPointF(crop_s.left(), top_hair_y), QPointF(crop_s.right(), top_hair_y))
        painter.drawLine(QPointF(crop_s.left(), chin_y), QPointF(crop_s.right(), chin_y))

        # Center line
        cx = crop_s.center().x()
        center_pen = QPen(QColor("#90CAF9"), 1, Qt.PenStyle.DotLine)
        painter.setPen(center_pen)
        painter.drawLine(QPointF(cx, crop_s.top()), QPointF(cx, crop_s.bottom()))

        # Guide labels
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        painter.setPen(QColor("#FFD54F"))
        painter.drawText(QPointF(crop_s.left() + 4, top_hair_y - 2), "Top of Head")
        painter.drawText(QPointF(crop_s.left() + 4, chin_y - 2), "Chin")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            crop_s = self._crop_screen_rect()
            if crop_s.contains(event.position()):
                self._dragging = True
                self._last_mouse_pos = event.position()
            else:
                # Click outside to move box center there
                norm_x = (event.position().x() - self._img_rect.left()) / self._img_rect.width()
                norm_y = (event.position().y() - self._img_rect.top()) / self._img_rect.height()
                self._crop_norm.moveCenter(QPointF(norm_x, norm_y))
                self._clamp_crop()
                self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            delta = event.position() - self._last_mouse_pos
            self._last_mouse_pos = event.position()
            dx_norm = delta.x() / self._img_rect.width()
            dy_norm = delta.y() / self._img_rect.height()
            self._crop_norm.translate(dx_norm, dy_norm)
            self._clamp_crop()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False


class AdjustCropDialog(QDialog):
    """Modal dialog allowing manual crop adjustment."""

    def __init__(
        self,
        pil_image: Image.Image,
        aspect_ratio: float,
        head_ratio: float = 0.75,
        initial_crop: Optional[Tuple[int, int, int, int]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adjust Passport Photo Crop")
        self.setMinimumSize(600, 620)
        self.result_crop: Optional[Tuple[int, int, int, int]] = None
        self.reset_to_auto = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_lbl = QLabel("Drag the green box to center the face. Align top of hair and chin with the yellow dashed lines.")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        self.overlay = CropOverlayWidget(pil_image, aspect_ratio, head_ratio, self)
        if initial_crop:
            self.overlay.set_crop_box_pixels(*initial_crop)
        layout.addWidget(self.overlay, stretch=1)

        # Size slider
        size_box = QHBoxLayout()
        size_box.addWidget(QLabel("Crop Size:"))
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(20, 100)
        self.size_slider.setValue(int(self.overlay._crop_norm.width() * 100))
        self.size_slider.valueChanged.connect(lambda v: self.overlay.set_zoom(v / 100.0))
        size_box.addWidget(self.size_slider)
        layout.addLayout(size_box)

        # Buttons
        btn_box = QHBoxLayout()

        self.auto_btn = QPushButton("↺ Auto Face Crop")
        self.auto_btn.setProperty("role", "danger")
        self.auto_btn.clicked.connect(self._on_auto_clicked)
        btn_box.addWidget(self.auto_btn)

        btn_box.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("✓ Apply Crop")
        self.apply_btn.setProperty("role", "success")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        btn_box.addWidget(self.apply_btn)

        layout.addLayout(btn_box)

    def _on_apply_clicked(self) -> None:
        self.result_crop = self.overlay.get_crop_box_pixels()
        self.reset_to_auto = False
        self.accept()

    def _on_auto_clicked(self) -> None:
        self.result_crop = None
        self.reset_to_auto = True
        self.accept()
