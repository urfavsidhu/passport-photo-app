"""AI background removal and replacement for passport photos.

Uses rembg with the isnet-general-use model loaded from the local models/ folder.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# rembg session (lazy, cached)
# ---------------------------------------------------------------------------

_session = None
_MAX_AI_SIZE = 2000  # Downscale longer side to this for speed


def _get_session():
    """Load the rembg session once, using models from the local folder."""
    global _session
    if _session is not None:
        return _session

    from app.settings_manager import resource_path

    models_dir = resource_path("models")
    if not models_dir.exists():
        models_dir.mkdir(parents=True, exist_ok=True)

    # Tell rembg / onnxruntime where to find model files
    os.environ["U2NET_HOME"] = str(models_dir)

    # Also set for ONNX runtime in case it looks for models
    os.environ["OMP_NUM_THREADS"] = "4"  # Limit threads for 8GB RAM PCs

    try:
        from rembg import new_session
        _session = new_session("isnet-general-use")
        logger.info("rembg session loaded (isnet-general-use) from %s", models_dir)
    except Exception as exc:
        # Try u2net as fallback
        try:
            _session = new_session("u2net")
            logger.info("rembg session loaded (u2net fallback) from %s", models_dir)
        except Exception:
            msg = (
                f"Could not load AI model.\n"
                f"Make sure model files exist in: {models_dir}\n"
                f"Run 'python tools/download_models.py' to download them.\n"
                f"Error: {exc}"
            )
            logger.error(msg)
            raise RuntimeError(msg) from exc
    return _session


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def remove_background(img: Image.Image) -> Image.Image:
    """Remove the background from a photo, returning an RGBA image.

    For speed, large images are downscaled before the AI step and
    the alpha mask is then upscaled back to original resolution.

    Args:
        img: Input PIL Image (RGB or RGBA).

    Returns:
        RGBA image with background removed and alpha cleaned.
    """
    session = _get_session()

    # Ensure RGB for processing
    if img.mode == "RGBA":
        # Composite on white first to handle any existing alpha
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        rgb_img = bg
    elif img.mode != "RGB":
        rgb_img = img.convert("RGB")
    else:
        rgb_img = img

    original_size = rgb_img.size
    need_upscale = max(original_size) > _MAX_AI_SIZE

    # Downscale for AI if image is very large
    if need_upscale:
        ratio = _MAX_AI_SIZE / max(original_size)
        small_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
        small_img = rgb_img.resize(small_size, Image.LANCZOS)
        logger.info("Downscaled %s -> %s for AI processing", original_size, small_size)
    else:
        small_img = rgb_img

    # Run rembg
    from rembg import remove
    result_small = remove(
        small_img,
        session=session,
        post_process_mask=True,
    )

    if need_upscale:
        # Extract alpha from small result and upscale it
        alpha_small = result_small.split()[3]
        alpha_full = alpha_small.resize(original_size, Image.LANCZOS)
        # Combine original RGB with upscaled alpha
        rgba = rgb_img.convert("RGBA")
        rgba.putalpha(alpha_full)
    else:
        rgba = result_small.convert("RGBA")

    # Clean the alpha channel
    rgba = _clean_alpha(rgba)

    # Decontaminate edge colors to remove halos
    rgba = _decontaminate_edges(rgba)

    return rgba


def _clean_alpha(rgba: Image.Image) -> Image.Image:
    """Remove tiny specks and slightly feather edges in the alpha channel."""
    alpha = np.array(rgba.split()[3])

    # Remove small specks: threshold to binary, then back
    # Pixels with very low alpha (< 20) become 0, very high (> 235) become 255
    cleaned = alpha.copy()
    cleaned[cleaned < 20] = 0
    cleaned[cleaned > 235] = 255

    # Remove small isolated opaque regions (noise specks)
    try:
        import cv2
        # Find connected components in the binary mask
        binary = (cleaned > 127).astype(np.uint8) * 255
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        # Remove components smaller than 0.1% of total image area
        min_area = max(100, alpha.shape[0] * alpha.shape[1] * 0.001)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] < min_area:
                cleaned[labels == i] = 0
    except ImportError:
        pass

    # Slight feathering on edges (1px Gaussian blur on alpha only)
    alpha_img = Image.fromarray(cleaned)
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=0.5))

    rgba_copy = rgba.copy()
    rgba_copy.putalpha(alpha_img)
    return rgba_copy


def _decontaminate_edges(rgba: Image.Image) -> Image.Image:
    """Remove color halos (white/green fringes) from semi-transparent edges.

    For edge pixels (alpha between 10 and 245), push the color toward
    the nearest fully-opaque pixel color to remove background color bleeding.
    """
    arr = np.array(rgba, dtype=np.float32)
    alpha = arr[:, :, 3]

    # Find edge pixels (semi-transparent)
    edge_mask = (alpha > 10) & (alpha < 245)
    if not np.any(edge_mask):
        return rgba

    # Find fully opaque interior pixels
    opaque_mask = alpha >= 245

    if not np.any(opaque_mask):
        return rgba

    try:
        import cv2
        # Dilate the opaque region to get "nearest interior color" for edges
        kernel = np.ones((5, 5), np.uint8)
        opaque_uint8 = opaque_mask.astype(np.uint8) * 255

        # For each edge pixel, replace its color with the nearest opaque color
        # We do this by inpainting: create an image with only opaque pixels,
        # then dilate/blur to fill edge regions
        rgb = arr[:, :, :3].copy()
        inpaint_mask = (~opaque_mask).astype(np.uint8) * 255

        # Simple approach: repeatedly dilate opaque colors into transparent regions
        for _ in range(3):
            dilated = cv2.dilate(rgb * (opaque_mask | edge_mask)[:, :, np.newaxis],
                                 kernel, iterations=1)
            dilated_mask = cv2.dilate(opaque_uint8, kernel, iterations=1) > 0
            
            # Only replace edge pixels
            replace = edge_mask & dilated_mask
            rgb[replace] = dilated[replace]

        arr[:, :, :3] = rgb
        return Image.fromarray(arr.astype(np.uint8), "RGBA")

    except Exception as exc:
        logger.debug("Edge decontamination skipped: %s", exc)
        return rgba


def apply_background(rgba: Image.Image, hex_color: str) -> Image.Image:
    """Composite an RGBA image onto a solid background color.

    Args:
        rgba: RGBA image with transparent background.
        hex_color: Background color as hex string (e.g. '#FFFFFF').

    Returns:
        RGB image with solid background.
    """
    # Parse hex color
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

    # Create background and composite
    background = Image.new("RGBA", rgba.size, (r, g, b, 255))
    composite = Image.alpha_composite(background, rgba.convert("RGBA"))
    return composite.convert("RGB")
