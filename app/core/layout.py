"""Print sheet layout — arrange passport photos on paper.

Pure Pillow module (no Qt). Computes exact pixel layouts from mm dimensions,
arranges photos in a grid, draws optional cut marks, and saves/exports sheets.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mm_to_px(mm: float, dpi: int) -> int:
    """Convert millimeters to pixels at a given DPI."""
    return round(mm / 25.4 * dpi)


def px_to_mm(px: int, dpi: int) -> float:
    """Convert pixels to millimeters at a given DPI."""
    return px * 25.4 / dpi


# ---------------------------------------------------------------------------
# Grid calculation
# ---------------------------------------------------------------------------

def _calc_grid(
    paper_w_px: int,
    paper_h_px: int,
    photo_w_px: int,
    photo_h_px: int,
    gap_px: int,
    margin_px: int,
) -> Tuple[int, int]:
    """Calculate how many photos fit in a grid.

    Returns:
        (cols, rows) count.
    """
    usable_w = paper_w_px - 2 * margin_px
    usable_h = paper_h_px - 2 * margin_px

    if usable_w < photo_w_px or usable_h < photo_h_px:
        return (0, 0)

    cols = 1 + (usable_w - photo_w_px) // (photo_w_px + gap_px)
    rows = 1 + (usable_h - photo_h_px) // (photo_h_px + gap_px)

    return (max(cols, 0), max(rows, 0))


# ---------------------------------------------------------------------------
# Cut marks
# ---------------------------------------------------------------------------

def _draw_cut_marks(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    w: int, h: int,
    mark_len: int = 15,
    color: str = "#BBBBBB",
    width: int = 1,
) -> None:
    """Draw L-shaped crop marks at each corner of a photo position."""
    corners = [
        # (corner_x, corner_y, horizontal_dir, vertical_dir)
        (x, y, -1, -1),                    # top-left
        (x + w, y, +1, -1),                # top-right
        (x, y + h, -1, +1),                # bottom-left
        (x + w, y + h, +1, +1),            # bottom-right
    ]
    gap = 3  # Gap between mark and photo edge

    for cx, cy, hdir, vdir in corners:
        # Horizontal mark
        hx_start = cx + gap * hdir
        hx_end = cx + (gap + mark_len) * hdir
        draw.line([(hx_start, cy), (hx_end, cy)], fill=color, width=width)

        # Vertical mark
        vy_start = cy + gap * vdir
        vy_end = cy + (gap + mark_len) * vdir
        draw.line([(cx, vy_start), (cx, vy_end)], fill=color, width=width)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_sheets(
    photo: Image.Image,
    paper_mm: Tuple[float, float],
    dpi: int = 300,
    copies: int = 8,
    gap_mm: float = 2.0,
    margin_mm: float = 5.0,
    min_printer_margin_mm: float = 3.0,
    cut_lines: bool = True,
    orientation: str = "auto",
) -> List[Image.Image]:
    """Build print sheets with the passport photo arranged in a grid.

    Args:
        photo: The passport photo (RGB, already at correct pixel size).
        paper_mm: Paper size as (width_mm, height_mm).
        dpi: Print DPI.
        copies: Total number of copies to place.
        gap_mm: Gap between photos in mm.
        margin_mm: Page margin in mm.
        min_printer_margin_mm: Minimum allowable printer margin in mm (default 3.0).
            The layout will never silently reduce margins below this threshold.
        cut_lines: Whether to draw cut marks.
        orientation: 'portrait', 'landscape', or 'auto' (pick best fit).

    Returns:
        List of sheet images (RGB) with correct DPI metadata.
    """
    photo_w_px, photo_h_px = photo.size
    gap_px = mm_to_px(gap_mm, dpi)

    # Respect min_printer_margin_mm: never go below this margin
    effective_margin_mm = max(margin_mm, min_printer_margin_mm)
    margin_px = mm_to_px(effective_margin_mm, dpi)

    pw_mm, ph_mm = paper_mm

    # Possible paper dimensions (portrait and landscape)
    p_port = (mm_to_px(min(pw_mm, ph_mm), dpi), mm_to_px(max(pw_mm, ph_mm), dpi))
    p_land = (mm_to_px(max(pw_mm, ph_mm), dpi), mm_to_px(min(pw_mm, ph_mm), dpi))

    # Test candidate configurations: (per_sheet, cols, rows, paper_w, paper_h, rotate_photo_90)
    candidates = []

    if orientation in ("auto", "portrait"):
        # Upright photo on portrait paper
        c, r = _calc_grid(p_port[0], p_port[1], photo_w_px, photo_h_px, gap_px, margin_px)
        candidates.append((c * r, c, r, p_port[0], p_port[1], False))
        # Rotated photo (90 deg) on portrait paper
        c_r, r_r = _calc_grid(p_port[0], p_port[1], photo_h_px, photo_w_px, gap_px, margin_px)
        candidates.append((c_r * r_r, c_r, r_r, p_port[0], p_port[1], True))

    if orientation in ("auto", "landscape"):
        # Upright photo on landscape paper
        c, r = _calc_grid(p_land[0], p_land[1], photo_w_px, photo_h_px, gap_px, margin_px)
        candidates.append((c * r, c, r, p_land[0], p_land[1], False))
        # Rotated photo (90 deg) on landscape paper
        c_r, r_r = _calc_grid(p_land[0], p_land[1], photo_h_px, photo_w_px, gap_px, margin_px)
        candidates.append((c_r * r_r, c_r, r_r, p_land[0], p_land[1], True))

    # Pick candidate that maximizes photos per sheet (preferring unrotated photo on tie)
    candidates.sort(key=lambda x: (x[0], not x[5]), reverse=True)
    best = candidates[0]
    per_sheet, cols, rows, paper_w_px, paper_h_px, rotate_photo = best

    # Prepare photo (rotate 90 deg if optimal)
    if rotate_photo:
        placed_photo = photo.rotate(90, expand=True)
        cur_w_px, cur_h_px = placed_photo.size
    else:
        placed_photo = photo
        cur_w_px, cur_h_px = photo_w_px, photo_h_px

    if per_sheet == 0:
        logger.warning("Photo is too large for the paper size!")
        sheet = Image.new("RGB", (paper_w_px, paper_h_px), (255, 255, 255))
        x = (paper_w_px - cur_w_px) // 2
        y = (paper_h_px - cur_h_px) // 2
        if x >= 0 and y >= 0:
            sheet.paste(placed_photo, (x, y))
        sheet.info["dpi"] = (dpi, dpi)
        return [sheet]

    # Calculate number of sheets needed
    num_sheets = (copies + per_sheet - 1) // per_sheet
    remaining = copies

    # Center the grid on the paper
    grid_w = cols * cur_w_px + (cols - 1) * gap_px
    grid_h = rows * cur_h_px + (rows - 1) * gap_px
    offset_x = (paper_w_px - grid_w) // 2
    offset_y = (paper_h_px - grid_h) // 2

    logger.info(
        "Layout: %dx%d grid (%d per sheet), %d sheets, rotated=%s",
        cols, rows, per_sheet, num_sheets, rotate_photo,
    )

    sheets = []
    for sheet_idx in range(num_sheets):
        sheet = Image.new("RGB", (paper_w_px, paper_h_px), (255, 255, 255))
        draw = ImageDraw.Draw(sheet) if cut_lines else None

        count_on_sheet = min(remaining, per_sheet)
        placed = 0

        for row in range(rows):
            for col in range(cols):
                if placed >= count_on_sheet:
                    break

                x = offset_x + col * (cur_w_px + gap_px)
                y = offset_y + row * (cur_h_px + gap_px)

                sheet.paste(placed_photo, (x, y))
                placed += 1

                if draw and cut_lines:
                    _draw_cut_marks(draw, x, y, cur_w_px, cur_h_px)

            if placed >= count_on_sheet:
                break

        remaining -= count_on_sheet
        sheet.info["dpi"] = (dpi, dpi)
        sheets.append(sheet)

    return sheets


def save_sheet(
    sheet: Image.Image,
    path: Path,
    fmt: str = "png",
    dpi: int = 300,
    jpg_quality: int = 95,
) -> Path:
    """Save a sheet image to disk.

    Args:
        sheet: The sheet image.
        path: Output file path (extension will be corrected).
        fmt: Output format ('png', 'jpg', or 'pdf').
        dpi: DPI for the output file.
        jpg_quality: JPEG quality (1-100).

    Returns:
        The actual path the file was saved to.
    """
    path = Path(path)
    fmt = fmt.lower().strip(".")

    if fmt == "jpg" or fmt == "jpeg":
        path = path.with_suffix(".jpg")
        # Convert to RGB if needed (JPEG doesn't support alpha)
        if sheet.mode != "RGB":
            sheet = sheet.convert("RGB")
        sheet.save(str(path), "JPEG", quality=jpg_quality, dpi=(dpi, dpi))

    elif fmt == "pdf":
        path = path.with_suffix(".pdf")
        if sheet.mode != "RGB":
            sheet = sheet.convert("RGB")
        sheet.save(str(path), "PDF", resolution=dpi)

    else:  # PNG
        path = path.with_suffix(".png")
        sheet.save(str(path), "PNG", dpi=(dpi, dpi))

    logger.info("Sheet saved: %s", path)
    return path
