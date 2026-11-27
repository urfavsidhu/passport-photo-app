"""Model download script for Passport Photo App.

Downloads the required ONNX models for offline background removal into the
local models/ directory so the application works completely offline.
"""

import os
import sys
import urllib.request
from pathlib import Path

# URLs for offline models (rembg ONNX models + MediaPipe face detector)
MODEL_URLS = {
    "isnet-general-use.onnx": [
        "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
        "https://huggingface.co/danielgatis/rembg/resolve/main/isnet-general-use.onnx",
    ],
    "u2net.onnx": [
        "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
        "https://huggingface.co/danielgatis/rembg/resolve/main/u2net.onnx",
    ],
    "blaze_face_short_range.tflite": [
        "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    ],
}


def download_file_with_progress(url: str, dest_path: Path) -> bool:
    """Download a file with console progress indicator."""
    print(f"Connecting to: {url}")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            block_size = 1024 * 1024  # 1 MB

            temp_path = dest_path.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        mb_down = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        sys.stdout.write(f"\r  [{pct:5.1f}%] {mb_down:6.1f} MB / {mb_total:6.1f} MB")
                        sys.stdout.flush()

            sys.stdout.write("\n")
            temp_path.replace(dest_path)
            print(f"  Successfully saved to: {dest_path}")
            return True
    except Exception as exc:
        print(f"\n  Download error: {exc}")
        if dest_path.with_suffix(".tmp").exists():
            dest_path.with_suffix(".tmp").unlink()
        return False


def main() -> None:
    # Resolve models directory relative to project root
    project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print(" Passport Photo App — Offline Model Downloader")
    print(f" Target folder: {models_dir}")
    print("==================================================\n")

    # Download rembg models + MediaPipe face detector
    target_models = [
        ("isnet-general-use.onnx", 10 * 1024 * 1024),
        ("u2net.onnx", 10 * 1024 * 1024),
        ("blaze_face_short_range.tflite", 100 * 1024),
    ]

    for filename, min_size in target_models:
        dest = models_dir / filename
        if dest.exists() and dest.stat().st_size > min_size:
            print(f"[OK] Model already present: {filename} ({dest.stat().st_size / (1024*1024):.2f} MB)")
            continue

        print(f"\nDownloading {filename}...")
        urls = MODEL_URLS.get(filename, [])
        success = False
        for url in urls:
            if download_file_with_progress(url, dest):
                success = True
                break

        if not success:
            print(f"[WARNING] Could not download {filename} from any mirror.")

    print("\nDownload process completed.")


if __name__ == "__main__":
    main()
