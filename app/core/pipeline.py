"""Passport photo processing pipeline.

Orchestrates: load → background removal → enhance → face crop → composite → layout.
Caches intermediate results so the UI can re-apply color/enhance/layout changes
without re-running the expensive AI background removal.
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""
    final_photo: Optional[Image.Image] = None     # Single passport photo (RGB)
    sheets: List[Image.Image] = field(default_factory=list)  # Print sheets
    warnings: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)
    settings_snapshot: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    num_sheets: int = 0
    copies: int = 0
    photo_size_mm: Tuple[float, float] = (35.0, 45.0)
    face_box: Optional[Any] = None

    @property
    def has_blocking_issues(self) -> bool:
        """True if there are safety or quality defects that prevent printing."""
        return len(self.blocking_issues) > 0


class PassportPipeline:
    """Full passport photo processing pipeline with caching.

    After the first run, intermediate results (RGBA cutout, face box)
    are cached so changes to enhancement, background color, or layout
    settings can be applied instantly without re-running the AI model.
    """

    def __init__(self) -> None:
        # Cached intermediate results
        self._original: Optional[Image.Image] = None     # Original loaded image (RGB)
        self._rgba_cutout: Optional[Image.Image] = None   # After background removal (RGBA)
        self._face_box: Optional[Any] = None               # Detected face
        self._alpha_mask: Optional[Image.Image] = None     # Alpha channel
        self._cropped: Optional[Image.Image] = None        # After face crop (RGBA)
        self._enhanced_cropped: Optional[Image.Image] = None # After enhancement on cropped (RGBA)
        self._blocking_issues: List[str] = []
        self._face_warnings: List[str] = []
        self._manual_crop_box: Optional[Tuple[int, int, int, int]] = None

    def run(
        self,
        image: Image.Image,
        settings: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> PipelineResult:
        """Run the full pipeline.

        Args:
            image: Input PIL Image.
            settings: Dict with keys from SettingsManager.
            progress_callback: Optional callback(step_name, percent).

        Returns:
            PipelineResult with final photo, sheets, warnings, blocking_issues, and timings.
        """
        result = PipelineResult()
        timings = {}
        self._blocking_issues = []
        self._face_warnings = []
        self._manual_crop_box = None

        def report(step: str, pct: int) -> None:
            if progress_callback:
                progress_callback(step, pct)

        # --- Step 1: Load and fix EXIF rotation ---
        report("Loading image...", 5)
        t0 = time.time()
        self._original = ImageOps.exif_transpose(image)
        if self._original.mode not in ("RGB", "RGBA"):
            self._original = self._original.convert("RGB")
        
        # Optimize high-res camera uploads (e.g. 4000x3000) to max 1600px for speed & memory
        max_dim = max(self._original.size)
        if max_dim > 1600:
            scale_ratio = 1600.0 / max_dim
            opt_size = (int(round(self._original.width * scale_ratio)), int(round(self._original.height * scale_ratio)))
            self._original = self._original.resize(opt_size, Image.LANCZOS)
            logger.info("Resized high-res image %s -> %s for fast processing", (self._original.width, self._original.height), opt_size)

        timings["load"] = time.time() - t0
        logger.info("Image loaded: %s, size=%s", self._original.mode, self._original.size)

        # --- Step 2: Remove background ---
        report("Removing background...", 15)
        t0 = time.time()
        from app.core.background import remove_background
        try:
            self._rgba_cutout = remove_background(self._original)
            self._alpha_mask = self._rgba_cutout.split()[3]
            
            # Check alpha coverage
            import numpy as np
            alpha_arr = np.array(self._alpha_mask)
            opaque_count = int(np.sum(alpha_arr > 30))
            total_count = alpha_arr.size
            coverage = opaque_count / total_count if total_count > 0 else 0.0

            if coverage < 0.05:
                issue = "Background cutout failed: subject alpha coverage is under 5% (subject not clearly separated from background)."
                self._blocking_issues.append(issue)
                logger.warning(issue)
            elif coverage > 0.98:
                issue = "Background removal failed: entire background retained (alpha coverage > 98%)."
                self._blocking_issues.append(issue)
                logger.warning(issue)

        except Exception as exc:
            issue = f"AI Background removal failed: {exc}"
            self._blocking_issues.append(issue)
            logger.error(issue)
            self._rgba_cutout = self._original.convert("RGBA")
            self._alpha_mask = self._rgba_cutout.split()[3]

        timings["background_removal"] = time.time() - t0
        logger.info("Background removed in %.1fs", timings["background_removal"])

        # --- Step 3: Detect face and crop ---
        report("Detecting face and framing...", 50)
        t0 = time.time()
        from app.core.face_crop import detect_face, crop_passport, NoFaceFoundError
        from app.settings_manager import photo_size_mm

        try:
            self._face_box, face_warnings = detect_face(self._rgba_cutout)
            self._face_warnings = list(face_warnings)

            # Check face size
            iw, ih = self._original.size
            face_area = self._face_box.width * self._face_box.height
            img_area = iw * ih
            if face_area < 0.03 * img_area or self._face_box.height < 0.12 * ih:
                issue = f"Detected face is too small ({self._face_box.width}x{self._face_box.height} px, < 3% of photo area). Please take a closer photo."
                self._blocking_issues.append(issue)
                logger.warning(issue)

        except NoFaceFoundError as exc:
            issue = "No human face detected in the photo. Please use a clear, well-lit photo."
            self._blocking_issues.append(issue)
            self._face_warnings = []
            logger.warning("No face found, using center crop fallback")
            self._face_box = None

        pw_mm, ph_mm = photo_size_mm(settings.get("photo_size", "35x45"))
        dpi = settings.get("dpi", 300)
        head_ratio = settings.get("head_ratio", 0.75)
        bg_hex = self._get_bg_hex(settings)

        self._cropped = self._execute_crop(pw_mm, ph_mm, dpi, head_ratio, bg_hex)
        timings["face_crop"] = time.time() - t0

        # --- Step 4: Enhance (run on the cropped small image for speed and precision) ---
        report("Enhancing photo...", 70)
        t0 = time.time()
        self._enhanced_cropped = self._apply_enhancements(self._cropped, settings)
        timings["enhance"] = time.time() - t0

        # --- Step 5: Composite on background ---
        report("Applying background...", 80)
        t0 = time.time()
        from app.core.background import apply_background
        if self._enhanced_cropped.mode == "RGBA":
            final_photo = apply_background(self._enhanced_cropped, bg_hex)
        else:
            final_photo = self._enhanced_cropped
        result.final_photo = final_photo
        timings["composite"] = time.time() - t0

        # --- Step 6: Build print sheets ---
        report("Building print layout...", 90)
        t0 = time.time()
        from app.core.layout import build_sheets
        from app.settings_manager import paper_size_mm

        pap_mm = paper_size_mm(settings.get("paper_size", "4x6"))
        result.sheets = build_sheets(
            photo=final_photo,
            paper_mm=pap_mm,
            dpi=dpi,
            copies=settings.get("copies", 8),
            gap_mm=settings.get("gap_mm", 2.0),
            margin_mm=settings.get("margin_mm", 5.0),
            min_printer_margin_mm=settings.get("min_printer_margin_mm", 3.0),
            cut_lines=settings.get("cut_lines", True),
            orientation=settings.get("paper_orientation", "auto"),
        )
        result.num_sheets = len(result.sheets)
        timings["layout"] = time.time() - t0

        result.blocking_issues = list(self._blocking_issues)
        result.warnings = list(self._face_warnings)
        result.settings_snapshot = dict(settings)
        result.timings = timings
        report("Done!", 100)

        total = sum(timings.values())
        logger.info("Pipeline complete in %.1fs: %s", total,
                     ", ".join(f"{k}={v:.1f}s" for k, v in timings.items()))

        return result

    # -------------------------------------------------------------------
    # Cheap re-apply functions (use cached RGBA cutout)
    # -------------------------------------------------------------------

    def reapply_crop_and_layout(
        self, settings: Dict[str, Any]
    ) -> Optional[PipelineResult]:
        """Re-crop and rebuild layout without re-running AI steps.

        Returns a PipelineResult with updated final_photo and sheets,
        while maintaining persistent blocking_issues and warnings.
        """
        if self._rgba_cutout is None:
            return None

        result = PipelineResult()
        from app.core.background import apply_background
        from app.core.layout import build_sheets
        from app.settings_manager import photo_size_mm, paper_size_mm

        pw_mm, ph_mm = photo_size_mm(settings.get("photo_size", "35x45"))
        dpi = settings.get("dpi", 300)
        head_ratio = settings.get("head_ratio", 0.75)
        bg_hex = self._get_bg_hex(settings)

        self._cropped = self._execute_crop(pw_mm, ph_mm, dpi, head_ratio, bg_hex)
        self._enhanced_cropped = self._apply_enhancements(self._cropped, settings)

        if self._enhanced_cropped.mode == "RGBA":
            result.final_photo = apply_background(self._enhanced_cropped, bg_hex)
        else:
            result.final_photo = self._enhanced_cropped

        pap_mm = paper_size_mm(settings.get("paper_size", "4x6"))
        result.sheets = build_sheets(
            photo=result.final_photo,
            paper_mm=pap_mm,
            dpi=dpi,
            copies=settings.get("copies", 8),
            gap_mm=settings.get("gap_mm", 2.0),
            margin_mm=settings.get("margin_mm", 5.0),
            min_printer_margin_mm=settings.get("min_printer_margin_mm", 3.0),
            cut_lines=settings.get("cut_lines", True),
            orientation=settings.get("paper_orientation", "auto"),
        )
        result.num_sheets = len(result.sheets)
        result.blocking_issues = list(self._blocking_issues)
        result.warnings = list(self._face_warnings)
        result.settings_snapshot = dict(settings)
        return result

    def set_manual_crop(self, crop_box: Optional[Tuple[int, int, int, int]]) -> None:
        """Set or clear manual crop box (x, y, w, h). If set, overrides automatic face crop."""
        self._manual_crop_box = crop_box
        if crop_box is not None:
            # User explicitly framed the crop; clear face missing/small blocking issues
            self._blocking_issues = [
                issue for issue in self._blocking_issues
                if "no human face" not in issue.lower() and "too small" not in issue.lower()
            ]

    def _execute_crop(
        self, pw_mm: float, ph_mm: float, dpi: int, head_ratio: float, bg_hex: str
    ) -> Image.Image:
        """Execute face crop, manual crop, or center crop."""
        from app.core.face_crop import crop_passport
        out_w = round(pw_mm / 25.4 * dpi)
        out_h = round(ph_mm / 25.4 * dpi)

        if self._manual_crop_box is not None and self._rgba_cutout is not None:
            # Manual crop box (x, y, w, h)
            mx, my, mw, mh = self._manual_crop_box
            cropped = self._rgba_cutout.crop((mx, my, mx + mw, my + mh))
            return cropped.resize((out_w, out_h), Image.LANCZOS)

        if self._face_box is not None and self._rgba_cutout is not None:
            return crop_passport(
                self._rgba_cutout, self._face_box, self._alpha_mask,
                pw_mm, ph_mm, dpi, head_ratio, bg_hex,
            )

        # Fallback: center crop to target aspect ratio
        source = self._rgba_cutout if self._rgba_cutout is not None else self._original
        return self._center_crop(source, pw_mm, ph_mm, dpi)

    def has_cached_data(self) -> bool:
        """Check if there is cached data from a previous run."""
        return self._rgba_cutout is not None

    def get_original(self) -> Optional[Image.Image]:
        """Return the original loaded image."""
        return self._original

    def get_rgba_cutout(self) -> Optional[Image.Image]:
        """Return the cached RGBA cutout."""
        return self._rgba_cutout

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _apply_enhancements(rgba: Image.Image, settings: Dict[str, Any]) -> Image.Image:
        """Apply enhancement settings to an RGBA image."""
        from app.core.enhance import apply_all_adjustments
        return apply_all_adjustments(
            rgba,
            brightness=settings.get("brightness", 0),
            contrast=settings.get("contrast", 0),
            warmth=settings.get("warmth", 0),
            shadow_lift=settings.get("shadow_lift", 0),
            do_auto_enhance=settings.get("auto_enhance", False),
        )

    @staticmethod
    def _get_bg_hex(settings: Dict[str, Any]) -> str:
        """Get background hex color from settings."""
        from app.settings_manager import background_hex
        bg = settings.get("background", "white")
        if bg == "custom":
            return settings.get("custom_bg_color", "#FFFFFF")
        return background_hex(bg)

    @staticmethod
    def _center_crop(image: Image.Image, w_mm: float, h_mm: float, dpi: int) -> Image.Image:
        """Fallback center crop when no face is detected."""
        out_w = round(w_mm / 25.4 * dpi)
        out_h = round(h_mm / 25.4 * dpi)
        aspect = out_w / out_h

        iw, ih = image.size
        img_aspect = iw / ih

        if img_aspect > aspect:
            # Image is wider: crop width
            new_w = int(ih * aspect)
            left = (iw - new_w) // 2
            cropped = image.crop((left, 0, left + new_w, ih))
        else:
            # Image is taller: crop height
            new_h = int(iw / aspect)
            top = (ih - new_h) // 3  # Bias toward upper third (head region)
            cropped = image.crop((0, top, iw, top + new_h))

        return cropped.resize((out_w, out_h), Image.LANCZOS)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli_main() -> None:
    """CLI test: python -m app.core.pipeline <image_path>"""
    import argparse
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Passport photo pipeline CLI")
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--photo-size", default="35x45", help="Photo size (e.g. 35x45)")
    parser.add_argument("--paper-size", default="4x6", help="Paper size (e.g. 4x6, A4)")
    parser.add_argument("--copies", type=int, default=8, help="Number of copies")
    parser.add_argument("--dpi", type=int, default=300, help="Output DPI")
    parser.add_argument("--background", default="white", help="Background color")
    parser.add_argument("--output", default=None, help="Output directory")
    args = parser.parse_args()

    from app.settings_manager import resource_path, user_data_dir, DEFAULT_SETTINGS

    # Build settings dict
    settings = dict(DEFAULT_SETTINGS)
    settings.update({
        "photo_size": args.photo_size,
        "paper_size": args.paper_size,
        "copies": args.copies,
        "dpi": args.dpi,
        "background": args.background,
    })

    # Determine output directory
    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = resource_path("data/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load image
    img_path = Path(args.image)
    if not img_path.exists():
        print(f"ERROR: File not found: {img_path}")
        sys.exit(1)

    print(f"Loading: {img_path}")
    image = Image.open(img_path)

    # Run pipeline
    pipeline = PassportPipeline()

    def progress(step: str, pct: int) -> None:
        print(f"  [{pct:3d}%] {step}")

    result = pipeline.run(image, settings, progress_callback=progress)

    # Save outputs
    if result.final_photo:
        photo_path = out_dir / f"{img_path.stem}_passport.png"
        result.final_photo.save(str(photo_path), "PNG", dpi=(args.dpi, args.dpi))
        print(f"Passport photo saved: {photo_path}")

    from app.core.layout import save_sheet
    for i, sheet in enumerate(result.sheets):
        sheet_path = out_dir / f"{img_path.stem}_sheet_{i + 1}.png"
        save_sheet(sheet, sheet_path, "png", args.dpi)
        print(f"Sheet {i + 1} saved: {sheet_path}")

    # Print warnings
    for w in result.warnings:
        print(f"WARNING: {w}")

    # Print timings
    print("\nTimings:")
    for step, t in result.timings.items():
        print(f"  {step}: {t:.2f}s")
    print(f"  TOTAL: {sum(result.timings.values()):.2f}s")


if __name__ == "__main__":
    _cli_main()
