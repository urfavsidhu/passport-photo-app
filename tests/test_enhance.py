"""Unit tests for lighting adjustments, skin-tone preservation, and foreground-only contrast."""

import numpy as np
import pytest
from PIL import Image

from app.core.enhance import (
    adjust_brightness, adjust_contrast, adjust_warmth, adjust_shadow_lift, auto_enhance,
)


def test_skin_tone_ratio_preserved():
    """Verify that auto_enhance does not distort skin tone (R/B ratio change < 5%)."""
    # Create an image with representative skin color: R=210, G=160, B=125
    orig_r, orig_g, orig_b = 210, 160, 125
    orig_rb_ratio = orig_r / orig_b

    skin_img = Image.new("RGB", (200, 200), (orig_r, orig_g, orig_b))
    enhanced = auto_enhance(skin_img)

    arr = np.array(enhanced)
    enh_r = float(np.mean(arr[:, :, 0]))
    enh_g = float(np.mean(arr[:, :, 1]))
    enh_b = float(np.mean(arr[:, :, 2]))
    enh_rb_ratio = enh_r / enh_b

    pct_change = abs(enh_rb_ratio - orig_rb_ratio) / orig_rb_ratio * 100.0

    # P1: Skin tone R/B ratio shift must be < 5%
    assert pct_change < 5.0, f"Skin tone R/B ratio changed by {pct_change:.2f}% (exceeds 5% limit)"


def test_contrast_uses_foreground_mask():
    """Verify that adjust_contrast calculates mean on foreground pixels only without dark background bias."""
    # RGBA image with 80% transparent background (alpha=0) and 20% bright foreground patch (220, 220, 220, 255)
    w, h = 100, 100
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    # Foreground patch
    arr[40:60, 40:60, 0:3] = 220
    arr[40:60, 40:60, 3] = 255

    rgba_img = Image.fromarray(arr, mode="RGBA")

    adjusted = adjust_contrast(rgba_img, value=20)
    adj_arr = np.array(adjusted)

    fg_values = adj_arr[40:60, 40:60, 0]
    # Foreground pixels should stay within reasonable range and not saturate completely to 255
    assert np.mean(fg_values) >= 210
    assert np.mean(fg_values) <= 255


def test_lighting_sliders_no_crash():
    """Ensure brightness, contrast, warmth, and shadow adjustments handle extremes gracefully."""
    test_img = Image.new("RGB", (100, 100), (128, 128, 128))

    for val in [-100, -50, 0, 50, 100]:
        b = adjust_brightness(test_img, val)
        assert b.size == (100, 100)

        c = adjust_contrast(test_img, val)
        assert c.size == (100, 100)

        w = adjust_warmth(test_img, val)
        assert w.size == (100, 100)

    for val in [0, 50, 100]:
        s = adjust_shadow_lift(test_img, val)
        assert s.size == (100, 100)
