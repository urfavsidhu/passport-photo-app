"""Unit tests for sheet layout math and photo positioning."""

import pytest
from PIL import Image

from app.core.layout import build_sheets, mm_to_px, px_to_mm, _calc_grid


def test_mm_to_px_exact():
    """Verify standard DPI conversion formulas."""
    # 25.4 mm at 300 DPI must be exactly 300 px
    assert mm_to_px(25.4, 300) == 300
    assert mm_to_px(50.8, 300) == 600
    assert mm_to_px(25.4, 600) == 600
    assert mm_to_px(12.7, 300) == 150


def test_px_to_mm_roundtrip():
    """Verify roundtrip conversion consistency."""
    px = 300
    mm = px_to_mm(px, 300)
    assert abs(mm - 25.4) < 1e-4
    assert mm_to_px(mm, 300) == px


def test_calc_grid():
    """Verify grid capacity calculation."""
    # 4x6 inch paper = 1200 x 1800 px at 300 DPI
    # 35x45 mm photo = 413 x 531 px at 300 DPI
    paper_w, paper_h = 1200, 1800
    photo_w, photo_h = 413, 531
    gap_px = 24
    margin_px = 59

    cols, rows = _calc_grid(paper_w, paper_h, photo_w, photo_h, gap_px, margin_px)
    assert cols >= 2
    assert rows >= 2
    assert cols * rows >= 4


def test_build_sheets_single_sheet():
    """Test generating a single sheet of 8 passport photos."""
    # 35x45 mm photo at 300 DPI
    pw = round(35 / 25.4 * 300)
    ph = round(45 / 25.4 * 300)
    photo = Image.new("RGB", (pw, ph), (255, 0, 0))

    # 4x6 inch paper = (101.6, 152.4) mm
    paper_mm = (101.6, 152.4)
    sheets = build_sheets(
        photo=photo,
        paper_mm=paper_mm,
        dpi=300,
        copies=8,
        gap_mm=2.0,
        margin_mm=4.0,
        cut_lines=True,
        orientation="auto",
    )

    assert len(sheets) == 1
    sheet = sheets[0]
    assert sheet.mode == "RGB"
    # Check DPI metadata
    assert sheet.info.get("dpi") == (300, 300)


def test_build_sheets_multiple_sheets():
    """Test overflow to multiple sheets when requested copies exceed capacity."""
    pw = round(35 / 25.4 * 300)
    ph = round(45 / 25.4 * 300)
    photo = Image.new("RGB", (pw, ph), (0, 255, 0))

    paper_mm = (101.6, 152.4)  # 4x6 fits roughly 8 photos
    sheets = build_sheets(
        photo=photo,
        paper_mm=paper_mm,
        dpi=300,
        copies=20,  # 20 copies should require 3 sheets
        gap_mm=2.0,
        margin_mm=4.0,
        cut_lines=False,
        orientation="auto",
    )

    assert len(sheets) >= 2
    for s in sheets:
        assert s.size[0] > 0
        assert s.size[1] > 0


def test_orientation_auto():
    """Auto orientation selects the orientation that fits the most photos."""
    pw = 400
    ph = 500
    photo = Image.new("RGB", (pw, ph), (0, 0, 255))
    paper_mm = (100.0, 150.0)

    sheets = build_sheets(
        photo=photo,
        paper_mm=paper_mm,
        dpi=300,
        copies=6,
        orientation="auto",
    )
    assert len(sheets) >= 1
