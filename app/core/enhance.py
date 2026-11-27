"""Image enhancement for passport photos.

Provides brightness, contrast, warmth, and shadow lift adjustments,
plus an auto-enhance function. All operations preserve the alpha channel
and only modify the subject (foreground) pixels.
"""

import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


def _split_foreground(image: Image.Image) -> tuple:
    """Split image into RGB array and alpha mask.

    Returns:
        (rgb_array, alpha_array_or_None, had_alpha)
    """
    if image.mode == "RGBA":
        arr = np.array(image)
        rgb = arr[:, :, :3].copy()
        alpha = arr[:, :, 3].copy()
        return rgb, alpha, True
    else:
        return np.array(image.convert("RGB")), None, False


def _merge_foreground(rgb: np.ndarray, alpha: Optional[np.ndarray], had_alpha: bool) -> Image.Image:
    """Merge RGB array with alpha mask back into a PIL Image."""
    if had_alpha and alpha is not None:
        rgba = np.dstack([rgb, alpha])
        return Image.fromarray(rgba, "RGBA")
    return Image.fromarray(rgb, "RGB")


def _apply_to_foreground(rgb: np.ndarray, alpha: Optional[np.ndarray],
                          func) -> np.ndarray:
    """Apply a function only to foreground (opaque) pixels.

    This ensures the background color stays exact when composited later.
    """
    result = func(rgb)

    if alpha is not None:
        # Only change pixels where alpha > 0
        mask = alpha > 0
        mask_3d = np.stack([mask] * 3, axis=-1)
        output = np.where(mask_3d, result, rgb)
        return output.astype(np.uint8)
    return result.astype(np.uint8)


# ---------------------------------------------------------------------------
# Individual adjustments (range: -100 to +100)
# ---------------------------------------------------------------------------

def adjust_brightness(image: Image.Image, value: int) -> Image.Image:
    """Adjust brightness of the foreground.

    Args:
        image: Input image (RGB or RGBA).
        value: Brightness adjustment, -100 (darker) to +100 (brighter).

    Returns:
        Adjusted image.
    """
    if value == 0:
        return image

    rgb, alpha, had_alpha = _split_foreground(image)

    # Map -100..+100 to a multiplier
    # -100 -> 0.0 (black), 0 -> 1.0, +100 -> 2.0
    factor = 1.0 + value / 100.0

    def adjust(arr):
        return np.clip(arr.astype(np.float32) * factor, 0, 255)

    rgb = _apply_to_foreground(rgb, alpha, adjust)
    return _merge_foreground(rgb, alpha, had_alpha)


def adjust_contrast(image: Image.Image, value: int) -> Image.Image:
    """Adjust contrast of the foreground.

    Args:
        image: Input image (RGB or RGBA).
        value: Contrast adjustment, -100 to +100.

    Returns:
        Adjusted image.
    """
    if value == 0:
        return image

    rgb, alpha, had_alpha = _split_foreground(image)

    # Factor: -100 -> 0.0, 0 -> 1.0, +100 -> 3.0
    if value >= 0:
        factor = 1.0 + value * 2.0 / 100.0
    else:
        factor = 1.0 + value / 100.0  # 0.0 to 1.0

    def adjust(arr):
        mean = np.mean(arr)
        return np.clip((arr.astype(np.float32) - mean) * factor + mean, 0, 255)

    rgb = _apply_to_foreground(rgb, alpha, adjust)
    return _merge_foreground(rgb, alpha, had_alpha)


def adjust_warmth(image: Image.Image, value: int) -> Image.Image:
    """Adjust color temperature (warmth) of the foreground.

    Positive values make the image warmer (more yellow/red),
    negative values make it cooler (more blue).

    Args:
        image: Input image (RGB or RGBA).
        value: Warmth adjustment, -100 to +100.

    Returns:
        Adjusted image.
    """
    if value == 0:
        return image

    rgb, alpha, had_alpha = _split_foreground(image)

    # Shift: warm adds red, removes blue; cool adds blue, removes red
    shift = value * 0.15  # Max shift of 15 per channel

    def adjust(arr):
        result = arr.astype(np.float32).copy()
        result[:, :, 0] = np.clip(result[:, :, 0] + shift, 0, 255)      # Red
        result[:, :, 2] = np.clip(result[:, :, 2] - shift, 0, 255)      # Blue
        result[:, :, 1] = np.clip(result[:, :, 1] + shift * 0.3, 0, 255)  # Slight green for warmth
        return result

    rgb = _apply_to_foreground(rgb, alpha, adjust)
    return _merge_foreground(rgb, alpha, had_alpha)


def adjust_shadow_lift(image: Image.Image, value: int) -> Image.Image:
    """Lift (brighten) shadows without affecting highlights.

    Args:
        image: Input image (RGB or RGBA).
        value: Shadow lift, 0 to +100 (negative values darken shadows).

    Returns:
        Adjusted image.
    """
    if value == 0:
        return image

    rgb, alpha, had_alpha = _split_foreground(image)

    # Shadow lift: apply a curve that raises dark values more than bright ones
    amount = value / 100.0 * 50.0  # Max lift of 50 levels

    def adjust(arr):
        result = arr.astype(np.float32)
        # Weight: dark pixels get more lift, bright pixels get none
        # weight = (1 - pixel/255)^2 * amount
        weight = ((255.0 - result) / 255.0) ** 2 * amount
        return np.clip(result + weight, 0, 255)

    rgb = _apply_to_foreground(rgb, alpha, adjust)
    return _merge_foreground(rgb, alpha, had_alpha)


# ---------------------------------------------------------------------------
# Auto-enhance
# ---------------------------------------------------------------------------

def auto_enhance(image: Image.Image) -> Image.Image:
    """Apply gentle auto-enhancement to the foreground.

    Uses CLAHE (Contrast Limited Adaptive Histogram Equalization) on the
    L channel in LAB color space, plus mild auto white balance.

    Args:
        image: Input image (RGB or RGBA).

    Returns:
        Enhanced image.
    """
    rgb, alpha, had_alpha = _split_foreground(image)

    # Create a mask for foreground pixels only
    if alpha is not None:
        fg_mask = alpha > 30
    else:
        fg_mask = np.ones(rgb.shape[:2], dtype=bool)

    # Convert to LAB for CLAHE
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)

    # Apply CLAHE to L channel (gentle: clipLimit=1.5)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    l_original = lab[:, :, 0].copy()
    l_enhanced = clahe.apply(lab[:, :, 0])

    # Apply only to foreground
    lab[:, :, 0] = np.where(fg_mask, l_enhanced, l_original)

    # Convert back to RGB
    enhanced_rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # Mild auto white balance (gray world assumption)
    enhanced_rgb = _auto_white_balance(enhanced_rgb, fg_mask)

    # Merge back only foreground
    if alpha is not None:
        mask_3d = np.stack([fg_mask] * 3, axis=-1)
        result = np.where(mask_3d, enhanced_rgb, rgb)
    else:
        result = enhanced_rgb

    return _merge_foreground(result.astype(np.uint8), alpha, had_alpha)


def _auto_white_balance(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Apply mild gray-world white balance to foreground pixels."""
    result = rgb.astype(np.float32)
    fg_pixels = result[mask]

    if len(fg_pixels) == 0:
        return rgb

    # Gray world: scale each channel so the mean is the overall mean
    means = fg_pixels.mean(axis=0)
    overall_mean = means.mean()

    if overall_mean < 1:
        return rgb

    scales = overall_mean / (means + 1e-6)
    # Limit the correction to avoid extreme shifts
    scales = np.clip(scales, 0.85, 1.15)

    for c in range(3):
        channel = result[:, :, c]
        channel[mask] = np.clip(channel[mask] * scales[c], 0, 255)
        result[:, :, c] = channel

    return result.astype(np.uint8)


def apply_all_adjustments(
    image: Image.Image,
    brightness: int = 0,
    contrast: int = 0,
    warmth: int = 0,
    shadow_lift: int = 0,
    do_auto_enhance: bool = False,
) -> Image.Image:
    """Apply all adjustments in sequence.

    Args:
        image: Input image (RGB or RGBA).
        brightness: -100 to +100.
        contrast: -100 to +100.
        warmth: -100 to +100.
        shadow_lift: -100 to +100.
        do_auto_enhance: If True, apply auto-enhance first.

    Returns:
        Adjusted image (always works from the original, non-destructive).
    """
    result = image.copy()

    if do_auto_enhance:
        result = auto_enhance(result)

    if brightness != 0:
        result = adjust_brightness(result, brightness)
    if contrast != 0:
        result = adjust_contrast(result, contrast)
    if warmth != 0:
        result = adjust_warmth(result, warmth)
    if shadow_lift != 0:
        result = adjust_shadow_lift(result, shadow_lift)

    return result
