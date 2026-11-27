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
# Printer info
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


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------

def print_sheet(
    sheet: Image.Image,
    printer_name: Optional[str] = None,
    dpi: int = 300,
    job_name: str = "Passport Photo",
) -> None:
    """Print a sheet image at exact physical size (100% scale).

    Uses the printer's DPI and physical offset to position the image
    so that sizes in mm are correct on paper.

    Args:
        sheet: PIL Image (RGB) to print.
        printer_name: Printer name. None for default printer.
        dpi: The DPI the sheet image was created at.
        job_name: Name for the print job.

    Raises:
        RuntimeError: If printing fails (friendly message).
    """
    try:
        import win32print
        import win32ui
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
        # Create device context
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        # Get printer capabilities
        caps = _get_printer_caps(hdc)
        printer_dpi_x = caps["dpi_x"]
        printer_dpi_y = caps["dpi_y"]

        logger.info(
            "Printer DPI: %dx%d, offsets: (%d, %d), page: %dx%d",
            printer_dpi_x, printer_dpi_y,
            caps["offset_x"], caps["offset_y"],
            caps["page_w"], caps["page_h"],
        )

        # Scale image pixels to printer pixels for exact physical size
        # If our image is at 300 DPI and printer is at 600 DPI,
        # each of our pixels should be 2 printer pixels
        img_w, img_h = sheet.size
        scale_x = printer_dpi_x / dpi
        scale_y = printer_dpi_y / dpi
        dest_w = int(img_w * scale_x)
        dest_h = int(img_h * scale_y)

        # Offset to account for unprintable margins
        # We place at (0,0) in printable area, the driver handles offset
        dest_x = 0
        dest_y = 0

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
) -> None:
    """Print multiple sheets as one print job.

    Args:
        sheets: List of PIL Images (RGB).
        printer_name: Printer name. None for default.
        dpi: The DPI the sheets were created at.
        job_name: Name for the print job.
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

        hdc.StartDoc(job_name)

        for i, sheet in enumerate(sheets):
            hdc.StartPage()

            if sheet.mode != "RGB":
                sheet = sheet.convert("RGB")

            img_w, img_h = sheet.size
            scale_x = printer_dpi_x / dpi
            scale_y = printer_dpi_y / dpi
            dest_w = int(img_w * scale_x)
            dest_h = int(img_h * scale_y)

            dib = ImageWin.Dib(sheet)
            dib.draw(hdc.GetHandleOutput(), (0, 0, dest_w, dest_h))

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
