"""Unit tests for face detection, cropping, and eye-level auto-rotation."""

import math
import pytest
from PIL import Image

from app.core.face_crop import (
    FaceBox, _auto_rotate, crop_passport,
)


def test_auto_rotate_levels_tilted_eyes():
    """Verify that auto-rotate calculates tilt and rotates to level the eye line (< 1.0 deg)."""
    # Create an image of 600x600
    img = Image.new("RGB", (600, 600), (240, 240, 240))
    alpha = Image.new("L", (600, 600), 255)

    # Place left eye at (250, 280) and right eye at (350, 310) -> tilted by ~16.7 degrees
    # dy = 30, dx = 100 -> angle = atan2(30, 100) = ~16.699 degrees
    left_eye = (250, 280)
    right_eye = (350, 310)

    initial_dy = right_eye[1] - left_eye[1]
    initial_dx = right_eye[0] - left_eye[0]
    initial_angle = math.degrees(math.atan2(initial_dy, initial_dx))
    assert abs(initial_angle - 16.7) < 0.1

    face_box = FaceBox(
        x=200,
        y=220,
        width=200,
        height=220,
        confidence=0.99,
        left_eye=left_eye,
        right_eye=right_eye,
        nose=(300, 330),
        mouth=(300, 380),
    )

    rotated_img, rotated_face, rotated_alpha = _auto_rotate(img, face_box, alpha)

    # Check alpha mask rotated to same size
    assert rotated_alpha.size == rotated_img.size

    # Check rotated eye landmarks
    r_left = rotated_face.left_eye
    r_right = rotated_face.right_eye

    new_dy = r_right[1] - r_left[1]
    new_dx = r_right[0] - r_left[0]
    final_angle = math.degrees(math.atan2(new_dy, new_dx))

    # P1: Tilt must be leveled to < 1.0 degree!
    assert abs(final_angle) < 1.0, f"Eye line tilt was not leveled: final angle is {final_angle:.2f} deg"


def test_crop_passport_dimensions():
    """Verify crop_passport produces exact output dimensions at specified DPI."""
    img = Image.new("RGB", (1000, 1000), (200, 200, 200))
    fb = FaceBox(x=400, y=380, width=200, height=240, confidence=0.95)

    cropped = crop_passport(
        image=img,
        face=fb,
        alpha_mask=None,
        photo_w_mm=35.0,
        photo_h_mm=45.0,
        dpi=300,
        head_ratio=0.75,
    )

    # 35x45 mm at 300 DPI = 413x531 px
    expected_w = round(35.0 / 25.4 * 300)
    expected_h = round(45.0 / 25.4 * 300)
    assert cropped.size == (expected_w, expected_h)
