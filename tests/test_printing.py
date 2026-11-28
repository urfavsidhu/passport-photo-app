"""Unit tests for printing accuracy, paper verification, and calibration sheets with mocked Windows DC."""

from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from app.printing.printer import (
    generate_calibration_sheet, print_sheet, verify_paper_size,
)


def test_generate_calibration_sheet():
    """Verify calibration sheet generation creates valid sheet with 50mm markings."""
    sheet = generate_calibration_sheet(paper_size="4x6", dpi=300)
    assert sheet is not None
    assert sheet.mode == "RGB"
    # 4x6 inches at 300 DPI = 1200x1800 or 1800x1200
    assert (sheet.size == (1200, 1800)) or (sheet.size == (1800, 1200))
    assert sheet.info.get("dpi") == (300, 300)


def test_verify_paper_size():
    """Verify paper size check compares printer driver dimensions against requested sheet."""
    mock_caps = {
        "phys_w": 1200,
        "phys_h": 1800,
        "dpi_x": 300,
        "dpi_y": 300,
    }
    # 4x6 is 101.6 x 152.4 mm (matches 1200/300*25.4 x 1800/300*25.4)
    ok_4x6, _ = verify_paper_size(mock_caps, "4x6")
    assert ok_4x6 is True

    # A4 is 210 x 297 mm -> should mismatch 4x6 paper
    ok_a4, _ = verify_paper_size(mock_caps, "A4")
    assert ok_a4 is False


def test_printer_physical_origin_offset():
    """Verify that print_sheet offsets drawing by (-PHYSICALOFFSETX, -PHYSICALOFFSETY)

    for 100% exact physical mapping without fit-to-page distortion.
    """
    sheet = Image.new("RGB", (1200, 1800), (255, 255, 255))

    mock_caps = {
        "dpi_x": 300,
        "dpi_y": 300,
        "offset_x": 45,   # Printable area is 45 px from physical paper left edge
        "offset_y": 60,   # Printable area is 60 px from physical paper top edge
        "printable_w": 1110,
        "printable_h": 1680,
        "phys_w": 1200,
        "phys_h": 1800,
        "page_w": 1110,
        "page_h": 1680,
    }

    recorded_rects = []

    mock_dc = MagicMock()
    mock_dc.StartDoc = MagicMock()
    mock_dc.StartPage = MagicMock()
    mock_dc.EndPage = MagicMock()
    mock_dc.EndDoc = MagicMock()
    mock_dc.DeleteDC = MagicMock()

    class MockImageWinDib:
        def __init__(self, image):
            self.image = image
        def draw(self, hdc, rect):
            recorded_rects.append(rect)

    with patch("app.printing.printer.list_printers", return_value=["Test Shop Printer"]), \
         patch("app.printing.printer.get_printer_caps", return_value=mock_caps), \
         patch("app.printing.printer._set_devmode_paper_and_orientation"), \
         patch("win32ui.CreateDC", return_value=mock_dc), \
         patch("PIL.ImageWin.Dib", MockImageWinDib):

        print_sheet(sheet, printer_name="Test Shop Printer", dpi=300)

    # Must record exactly one draw call
    assert len(recorded_rects) == 1
    dest_rect = recorded_rects[0]

    # Expected: dest_x = -45, dest_y = -60, dest_w = 1200, dest_h = 1800
    # Destination rect tuple: (dest_x, dest_y, dest_x + dest_w, dest_y + dest_h)
    expected_x = -45
    expected_y = -60
    assert dest_rect[0] == expected_x, f"Expected X origin {expected_x}, got {dest_rect[0]}"
    assert dest_rect[1] == expected_y, f"Expected Y origin {expected_y}, got {dest_rect[1]}"
    assert dest_rect[2] - dest_rect[0] == 1200, "Image width was distorted / not 100% scale"
    assert dest_rect[3] - dest_rect[1] == 1800, "Image height was distorted / not 100% scale"
