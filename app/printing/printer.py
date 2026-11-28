"""Windows printing for passport photo sheets.

Uses pywin32 (win32print, win32ui) and PIL.ImageWin to print images
at exact physical size (100% scale, no fit-to-page).
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Printer enumeration
# ---------------------------------------------------------------------------

def list_printers() -> List[str]:
    """List installed printer names.

    Returns:
        List of printer name strings. Empty list if pywin32 is not available.
    """
    try:
        import win32print
        printers = []
        for flags, desc, name, comment in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        ):
            printers.append(name)
        return printers
    except ImportError:
        logger.warning("pywin32 not installed — printing is not available")
        return []
    except Exception as exc:
        logger.error("Could not list printers: %s", exc)
        return []


def get_default_printer() -> Optional[str]:
    """Return the default printer name, or None."""
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except ImportError:
        return None
    except Exception as exc:
        logger.error("Could not get default printer: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Calibration Sheet Generator
# ---------------------------------------------------------------------------

def generate_calibration_sheet(
    paper_size: Union[str, Tuple[float, float]] = (101.6, 152.4),
    dpi: int = 300,
) -> Image.Image:
    """Generate a physical calibration sheet with mm rulers and passport box.

    The shopkeeper can print this at 100% scale, measure the 50mm lines
    with a physical ruler, and enter scale/offset corrections in settings.
    """
    from PIL import ImageDraw, ImageFont
    from app.settings_manager import paper_size_mm

    if isinstance(paper_size, str):
        paper_mm = paper_size_mm(paper_size)
    else:
        paper_mm = paper_size

    w_px = round(paper_mm[0] / 25.4 * dpi)
    h_px = round(paper_mm[1] / 25.4 * dpi)
    sheet = Image.new("RGB", (w_px, h_px), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    def mm2px(mm_val: float) -> int:
        return round(mm_val / 25.4 * dpi)

    # Outer 5mm border
    m5 = mm2px(5.0)
    draw.rectangle([(m5, m5), (w_px - m5, h_px - m5)], outline="#000000", width=2)

    # Title
    start_y = mm2px(12.0)
    draw.text((mm2px(10.0), start_y), "Passport Photo App — Print Calibration Sheet", fill="#000000")
    draw.text((mm2px(10.0), start_y + mm2px(5.0)), f"Paper: {paper_mm[0]:.0f}x{paper_mm[1]:.0f} mm | Native DPI: {dpi}", fill="#555555")

    # 50 mm Horizontal Ruler
    rx = mm2px(15.0)
    ry = start_y + mm2px(16.0)
    draw.line([(rx, ry), (rx + mm2px(50.0), ry)], fill="#000000", width=2)
    for mm_i in range(51):
        x_pos = rx + mm2px(mm_i)
        t_len = mm2px(4.0) if mm_i % 10 == 0 else (mm2px(2.5) if mm_i % 5 == 0 else mm2px(1.5))
        draw.line([(x_pos, ry), (x_pos, ry + t_len)], fill="#000000", width=1 if mm_i % 5 != 0 else 2)
        if mm_i % 10 == 0:
            draw.text((x_pos - mm2px(2.0), ry + t_len + mm2px(1.0)), f"{mm_i}", fill="#000000")
    draw.text((rx + mm2px(18.0), ry - mm2px(4.5)), "50 mm Horizontal Ruler", fill="#000000")

    # 50 mm Vertical Ruler
    vx = mm2px(15.0)
    vy = ry + mm2px(16.0)
    draw.line([(vx, vy), (vx, vy + mm2px(50.0))], fill="#000000", width=2)
    for mm_i in range(51):
        y_pos = vy + mm2px(mm_i)
        t_len = mm2px(4.0) if mm_i % 10 == 0 else (mm2px(2.5) if mm_i % 5 == 0 else mm2px(1.5))
        draw.line([(vx, y_pos), (vx + t_len, y_pos)], fill="#000000", width=1 if mm_i % 5 != 0 else 2)
        if mm_i % 10 == 0:
            draw.text((vx + t_len + mm2px(1.0), y_pos - mm2px(2.0)), f"{mm_i}", fill="#000000")
    draw.text((vx + mm2px(6.0), vy + mm2px(22.0)), "50 mm Vertical", fill="#000000")

    # 35 x 45 mm Passport Box
    bx = vx + mm2px(35.0)
    by = vy + mm2px(5.0)
    bw = mm2px(35.0)
    bh = mm2px(45.0)
    draw.rectangle([(bx, by), (bx + bw, by + bh)], outline="#2E7D32", width=3)
    draw.text((bx + mm2px(4.0), by + mm2px(15.0)), "Exact Passport Box", fill="#2E7D32")
    draw.text((bx + mm2px(6.0), by + mm2px(22.0)), "35 mm × 45 mm", fill="#2E7D32")

    # Instructions box at bottom
    iy = h_px - mm2px(24.0)
    instructions = [
        "How to use this sheet:",
        "1. Measure the 50 mm rulers and 35x45 mm box with a physical scale.",
        "2. If 50 mm ruler measures 49.0 mm: scale factor is 50.0 / 49.0 = 1.020.",
        "3. Enter measured scale and offset in Settings -> Calibration.",
    ]
    for idx, line in enumerate(instructions):
        draw.text((mm2px(10.0), iy + idx * mm2px(4.0)), line, fill="#333333")

    sheet.info["dpi"] = (dpi, dpi)
    return sheet


# ---------------------------------------------------------------------------
# Printer info & Device Capabilities
# ---------------------------------------------------------------------------

def _get_printer_caps(hdc) -> dict:
    """Get printer device capabilities from an HDC.

    Returns dict with keys: dpi_x, dpi_y, offset_x, offset_y,
    phys_w, phys_h, page_w, page_h (all in pixels).
    """
    import win32con

    # These constants may not be in win32con, define them
    LOGPIXELSX = 88
    LOGPIXELSY = 90
    PHYSICALOFFSETX = 112
    PHYSICALOFFSETY = 113
    PHYSICALWIDTH = 110
    PHYSICALHEIGHT = 111
    HORZRES = 8
    VERTRES = 10

    try:
        dpi_x = hdc.GetDeviceCaps(LOGPIXELSX)
        dpi_y = hdc.GetDeviceCaps(LOGPIXELSY)
        offset_x = hdc.GetDeviceCaps(PHYSICALOFFSETX)
        offset_y = hdc.GetDeviceCaps(PHYSICALOFFSETY)
        phys_w = hdc.GetDeviceCaps(PHYSICALWIDTH)
        phys_h = hdc.GetDeviceCaps(PHYSICALHEIGHT)
        page_w = hdc.GetDeviceCaps(HORZRES)
        page_h = hdc.GetDeviceCaps(VERTRES)
    except Exception as exc:
        logger.warning("Could not read all device caps: %s", exc)
        dpi_x = dpi_y = 300
        offset_x = offset_y = 0
        phys_w = page_w = 2550  # ~8.5 inches
        phys_h = page_h = 3300  # ~11 inches

    return {
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "phys_w": phys_w,
        "phys_h": phys_h,
        "page_w": page_w,
        "page_h": page_h,
    }


# Public alias for caps lookup
get_printer_caps = _get_printer_caps


def _set_devmode_paper_and_orientation(
    printer_name: str,
    sheet_size_px: Tuple[int, int],
    dpi: int = 300,
) -> Optional[Any]:
    """Configure DEVMODE paper orientation and dimensions to match sheet."""
    try:
        import win32print
        import win32con

        hprinter = win32print.OpenPrinter(printer_name)
        try:
            p_info = win32print.GetPrinter(hprinter, 2)
            devmode = p_info.get("pDevMode")
            if devmode:
                is_landscape = sheet_size_px[0] > sheet_size_px[1]
                devmode.Orientation = win32con.DMORIENT_LANDSCAPE if is_landscape else win32con.DMORIENT_PORTRAIT
                return devmode
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as exc:
        logger.debug("Could not configure DEVMODE: %s", exc)
    return None


def verify_paper_size(caps: dict, paper: Union[str, Tuple[int, int]], dpi: int = 300) -> Tuple[bool, str]:
    """Verify that the printer driver's physical paper size matches sheet dimensions."""
    if caps.get("dpi_x", 0) <= 0 or caps.get("dpi_y", 0) <= 0 or caps.get("phys_w", 0) <= 0 or caps.get("phys_h", 0) <= 0:
        return True, ""

    if isinstance(paper, str):
        from app.settings_manager import paper_size_mm
        w_mm, h_mm = paper_size_mm(paper)
        sheet_size_px = (round(w_mm / 25.4 * dpi), round(h_mm / 25.4 * dpi))
    else:
        sheet_size_px = paper

    sheet_w_mm = sheet_size_px[0] * 25.4 / dpi
    sheet_h_mm = sheet_size_px[1] * 25.4 / dpi
    drv_w_mm = caps["phys_w"] * 25.4 / caps["dpi_x"]
    drv_h_mm = caps["phys_h"] * 25.4 / caps["dpi_y"]

    min_sheet, max_sheet = min(sheet_w_mm, sheet_h_mm), max(sheet_w_mm, sheet_h_mm)
    min_drv, max_drv = min(drv_w_mm, drv_h_mm), max(drv_w_mm, drv_h_mm)

    diff_w = abs(min_sheet - min_drv)
    diff_h = abs(max_sheet - max_drv)

    if diff_w > 8.0 or diff_h > 8.0:
        msg = (
            f"Printer driver paper size ({min_drv:.0f} × {max_drv:.0f} mm) does not match "
            f"requested sheet ({min_sheet:.0f} × {max_sheet:.0f} mm)."
        )
        logger.warning(msg)
        return False, msg
    return True, ""


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------

def print_sheet(
    sheet: Image.Image,
    printer_name: Optional[str] = None,
    dpi: int = 300,
    job_name: str = "Passport Photo",
    calibration_scale_x: float = 1.0,
    calibration_scale_y: float = 1.0,
    calibration_offset_x_mm: float = 0.0,
    calibration_offset_y_mm: float = 0.0,
) -> None:
    """Print a sheet image at exact physical size (100% scale).

    Uses the printer's DPI and physical offset to position the image
    relative to physical paper corners (dest = -PHYSICALOFFSET).

    Args:
        sheet: PIL Image (RGB) to print.
        printer_name: Printer name. None for default printer.
        dpi: The DPI the sheet image was created at.
        job_name: Name for the print job.
        calibration_scale_x: Horizontal physical scale multiplier.
        calibration_scale_y: Vertical physical scale multiplier.
        calibration_offset_x_mm: Horizontal physical offset in mm.
        calibration_offset_y_mm: Vertical physical offset in mm.

    Raises:
        RuntimeError: If printing fails (friendly message).
    """
    try:
        import win32print
        import win32ui
        import win32con
        from PIL import ImageWin
    except ImportError as exc:
        raise RuntimeError(
            "Printing requires pywin32.\n"
            "Install it with: pip install pywin32\n"
            f"Error: {exc}"
        ) from exc

    # Get printer
    if not printer_name:
        printer_name = get_default_printer()
    if not printer_name:
        raise RuntimeError(
            "No printer found.\n"
            "Please install a printer or select one in Settings."
        )

    # Check if printer is available
    available = list_printers()
    if printer_name not in available:
        raise RuntimeError(
            f"Printer '{printer_name}' is not available.\n"
            f"Available printers: {', '.join(available) if available else 'None'}\n"
            "Please check the printer is online and try again."
        )

    logger.info("Printing to '%s' at %d DPI", printer_name, dpi)

    hdc = None
    try:
        # Configure printer driver devmode for sheet orientation
        devmode = _set_devmode_paper_and_orientation(printer_name, sheet.size, dpi)

        # Create device context
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        # Get printer capabilities
        caps = get_printer_caps(hdc)
        printer_dpi_x = caps["dpi_x"]
        printer_dpi_y = caps["dpi_y"]

        # Verify paper size matches sheet dimensions
        matches, paper_warn = verify_paper_size(caps, sheet.size, dpi)
        if not matches:
            logger.warning("Paper size mismatch: %s", paper_warn)

        logger.info(
            "Printer DPI: %dx%d, offsets: (%d, %d), page: %dx%d",
            printer_dpi_x, printer_dpi_y,
            caps["offset_x"], caps["offset_y"],
            caps["page_w"], caps["page_h"],
        )

        # Scale image pixels to printer pixels for exact physical size (100% scale)
        img_w, img_h = sheet.size
        scale_x = (printer_dpi_x / dpi) * calibration_scale_x
        scale_y = (printer_dpi_y / dpi) * calibration_scale_y
        dest_w = int(img_w * scale_x)
        dest_h = int(img_h * scale_y)

        # Offset to map to the top-left PHYSICAL paper corner
        cal_off_x_px = int(calibration_offset_x_mm / 25.4 * printer_dpi_x)
        cal_off_y_px = int(calibration_offset_y_mm / 25.4 * printer_dpi_y)
        dest_x = -caps["offset_x"] + cal_off_x_px
        dest_y = -caps["offset_y"] + cal_off_y_px

        # Start print job
        hdc.StartDoc(job_name)
        hdc.StartPage()

        # Create the bitmap and draw it
        if sheet.mode != "RGB":
            sheet = sheet.convert("RGB")

        dib = ImageWin.Dib(sheet)
        dib.draw(hdc.GetHandleOutput(), (dest_x, dest_y, dest_x + dest_w, dest_y + dest_h))

        hdc.EndPage()
        hdc.EndDoc()

        logger.info("Print job sent successfully")

    except Exception as exc:
        msg = str(exc)
        if "offline" in msg.lower() or "not ready" in msg.lower():
            raise RuntimeError(
                f"Printer '{printer_name}' appears to be offline.\n"
                "Please check the printer is turned on and connected."
            ) from exc
        raise RuntimeError(
            f"Printing failed.\n"
            f"Printer: {printer_name}\n"
            f"Please check the printer is working.\n"
            f"Technical details: {exc}"
        ) from exc
    finally:
        if hdc is not None:
            try:
                hdc.DeleteDC()
            except Exception:
                pass


def print_sheets(
    sheets: List[Image.Image],
    printer_name: Optional[str] = None,
    dpi: int = 300,
    job_name: str = "Passport Photos",
    calibration_scale_x: float = 1.0,
    calibration_scale_y: float = 1.0,
    calibration_offset_x_mm: float = 0.0,
    calibration_offset_y_mm: float = 0.0,
) -> None:
    """Print multiple sheets as one print job.

    Args:
        sheets: List of PIL Images (RGB).
        printer_name: Printer name. None for default.
        dpi: The DPI the sheets were created at.
        job_name: Name for the print job.
        calibration_scale_x: Horizontal scale multiplier.
        calibration_scale_y: Vertical scale multiplier.
        calibration_offset_x_mm: Horizontal offset in mm.
        calibration_offset_y_mm: Vertical offset in mm.
    """
    if not sheets:
        raise RuntimeError("No sheets to print.")

    try:
        import win32print
        import win32ui
        from PIL import ImageWin
    except ImportError as exc:
        raise RuntimeError(
            "Printing requires pywin32.\n"
            f"Error: {exc}"
        ) from exc

    if not printer_name:
        printer_name = get_default_printer()
    if not printer_name:
        raise RuntimeError("No printer found.")

    hdc = None
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        caps = _get_printer_caps(hdc)
        printer_dpi_x = caps["dpi_x"]
        printer_dpi_y = caps["dpi_y"]

        # Check paper size on first sheet
        matches, paper_warn = verify_paper_size(caps, sheets[0].size, dpi)
        if not matches:
            logger.warning("Paper size mismatch: %s", paper_warn)

        hdc.StartDoc(job_name)

        cal_off_x_px = int(calibration_offset_x_mm / 25.4 * printer_dpi_x)
        cal_off_y_px = int(calibration_offset_y_mm / 25.4 * printer_dpi_y)
        dest_x = -caps["offset_x"] + cal_off_x_px
        dest_y = -caps["offset_y"] + cal_off_y_px

        for i, sheet in enumerate(sheets):
            hdc.StartPage()

            if sheet.mode != "RGB":
                sheet = sheet.convert("RGB")

            img_w, img_h = sheet.size
            scale_x = (printer_dpi_x / dpi) * calibration_scale_x
            scale_y = (printer_dpi_y / dpi) * calibration_scale_y
            dest_w = int(img_w * scale_x)
            dest_h = int(img_h * scale_y)

            dib = ImageWin.Dib(sheet)
            dib.draw(hdc.GetHandleOutput(), (dest_x, dest_y, dest_x + dest_w, dest_y + dest_h))

            hdc.EndPage()
            logger.info("Printed sheet %d/%d", i + 1, len(sheets))

        hdc.EndDoc()
        logger.info("All %d sheets printed", len(sheets))

    except Exception as exc:
        raise RuntimeError(f"Printing failed: {exc}") from exc
    finally:
        if hdc is not None:
            try:
                hdc.DeleteDC()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# PDF fallback
# ---------------------------------------------------------------------------

def save_as_pdf(
    sheets: List[Image.Image],
    path: Path,
    dpi: int = 300,
) -> Path:
    """Save sheets as a multi-page PDF.

    Args:
        sheets: List of sheet images.
        path: Output PDF path.
        dpi: Resolution for the PDF.

    Returns:
        Path to the saved PDF.
    """
    path = Path(path)
    if not sheets:
        raise ValueError("No sheets to save")

    rgb_sheets = []
    for s in sheets:
        if s.mode != "RGB":
            rgb_sheets.append(s.convert("RGB"))
        else:
            rgb_sheets.append(s)

    if len(rgb_sheets) == 1:
        rgb_sheets[0].save(str(path), "PDF", resolution=dpi)
    else:
        rgb_sheets[0].save(
            str(path), "PDF", resolution=dpi,
            save_all=True, append_images=rgb_sheets[1:],
        )

    logger.info("Saved %d sheet(s) as PDF: %s", len(sheets), path)
    return path
