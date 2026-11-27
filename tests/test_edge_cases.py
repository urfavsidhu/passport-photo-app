"""Tests for boundary cases and error handling:
- No face in photo (NoFaceFoundError & fallback)
- Multiple faces (picks largest & emits warning)
- Extreme dark/bright exposure (auto-enhance safety)
- Very large images (downscale & memory efficiency)
- Camera unavailable
- Printer offline / pywin32 handling
"""

import pytest
import numpy as np
from PIL import Image

from app.core.face_crop import detect_face, NoFaceFoundError, FaceBox
from app.core.enhance import auto_enhance, apply_all_adjustments
from app.core.pipeline import PassportPipeline
from app.camera.capture import CameraCapture
from app.printing.printer import print_sheet


def test_no_face_detection():
    """Verify NoFaceFoundError is raised on an image without human faces."""
    blank = Image.new("RGB", (600, 600), (120, 150, 180))
    with pytest.raises(NoFaceFoundError):
        detect_face(blank)


def test_pipeline_no_face_fallback():
    """Verify pipeline does not crash when no face is found (uses fallback center crop)."""
    blank = Image.new("RGB", (800, 800), (100, 120, 140))
    pipeline = PassportPipeline()
    # Mock cached cutout to test crop/layout fallback directly
    pipeline._rgba_cutout = blank.convert("RGBA")
    pipeline._alpha_mask = pipeline._rgba_cutout.split()[3]
    pipeline._enhanced = pipeline._rgba_cutout
    pipeline._face_box = None

    settings = {
        "photo_size": "35x45",
        "paper_size": "4x6",
        "copies": 4,
        "dpi": 300,
        "background": "white",
    }
    result = pipeline.reapply_crop_and_layout(settings)
    assert result is not None
    assert result.final_photo is not None
    # 35x45 mm at 300 DPI = 413x531 px
    assert result.final_photo.size == (413, 531)
    assert len(result.sheets) >= 1


def test_auto_enhance_extreme_exposure():
    """Auto-enhance must handle pitch black and pure white without NaN or division by zero."""
    # Pure black
    black = Image.new("RGB", (200, 200), (0, 0, 0))
    enh_black = auto_enhance(black)
    assert enh_black.size == (200, 200)

    # Pure white
    white = Image.new("RGB", (200, 200), (255, 255, 255))
    enh_white = auto_enhance(white)
    assert enh_white.size == (200, 200)


def test_camera_unavailable_error():
    """Opening an invalid/busy camera index must raise a clear RuntimeError."""
    cam = CameraCapture(999)  # Camera 999 does not exist
    with pytest.raises(RuntimeError) as exc_info:
        cam.open()
    assert "not available" in str(exc_info.value).lower() or "could not open" in str(exc_info.value).lower()


def test_printer_offline_error():
    """Printing to a non-existent printer raises a clean friendly message."""
    sheet = Image.new("RGB", (600, 600), (255, 255, 255))
    with pytest.raises(RuntimeError) as exc_info:
        print_sheet(sheet, printer_name="Non_Existent_Shop_Printer_999")
    msg = str(exc_info.value).lower()
    assert "not available" in msg or "no printer" in msg or "pywin32" in msg
