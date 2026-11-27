"""Face detection and passport-photo cropping.

Uses MediaPipe Face Detection with OpenCV Haar cascade as fallback.
Crops the image to exact passport dimensions with the head properly
positioned according to head_ratio.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NoFaceFoundError(Exception):
    """Raised when no face can be detected in the image.

    Message is user-friendly (suitable for display in the UI).
    """
    def __init__(self, message: str = "No face found in the photo. Please use a clear, well-lit photo with the face visible."):
        super().__init__(message)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FaceBox:
    """Detected face bounding box and optional landmarks."""
    x: int          # left
    y: int          # top
    width: int
    height: int
    confidence: float = 0.0
    left_eye: Optional[Tuple[int, int]] = None   # (x, y)
    right_eye: Optional[Tuple[int, int]] = None   # (x, y)
    nose: Optional[Tuple[int, int]] = None
    mouth: Optional[Tuple[int, int]] = None


# ---------------------------------------------------------------------------
# Face detection
# ---------------------------------------------------------------------------

def _detect_mediapipe_tasks(rgb_array: np.ndarray) -> List[FaceBox]:
    """Detect faces using modern MediaPipe Tasks FaceDetector."""
    faces = []
    try:
        from app.settings_manager import resource_path
        model_path = resource_path("models/blaze_face_short_range.tflite")
        if not model_path.exists():
            return faces

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        import mediapipe as mp

        options = vision.FaceDetectorOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            min_detection_confidence=0.5,
        )
        detector = vision.FaceDetector.create_from_options(options)
        h, w = rgb_array.shape[:2]
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_array)
        res = detector.detect(mp_img)

        for det in res.detections:
            bb = det.bounding_box
            fx = max(0, bb.origin_x)
            fy = max(0, bb.origin_y)
            fw = min(bb.width, w - fx)
            fh = min(bb.height, h - fy)

            left_eye = right_eye = nose = mouth = None
            if len(det.keypoints) >= 4:
                kp0 = (int(det.keypoints[0].x * w), int(det.keypoints[0].y * h))
                kp1 = (int(det.keypoints[1].x * w), int(det.keypoints[1].y * h))
                if kp0[0] < kp1[0]:
                    left_eye, right_eye = kp0, kp1
                else:
                    left_eye, right_eye = kp1, kp0

                if len(det.keypoints) > 2:
                    nose = (int(det.keypoints[2].x * w), int(det.keypoints[2].y * h))
                if len(det.keypoints) > 3:
                    mouth = (int(det.keypoints[3].x * w), int(det.keypoints[3].y * h))

            score = det.categories[0].score if det.categories else 0.85
            faces.append(FaceBox(
                x=fx, y=fy, width=fw, height=fh,
                confidence=float(score),
                left_eye=left_eye, right_eye=right_eye,
                nose=nose, mouth=mouth,
            ))
        if faces:
            logger.info("MediaPipe Tasks detected %d face(s)", len(faces))
    except Exception as exc:
        logger.debug("MediaPipe Tasks detection skipped: %s", exc)
    return faces


def _detect_mediapipe_solutions(rgb_array: np.ndarray) -> List[FaceBox]:
    """Detect faces using legacy MediaPipe Solutions FaceDetection."""
    faces = []
    try:
        import mediapipe as mp
        if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_detection"):
            return faces

        mp_face = mp.solutions.face_detection
        with mp_face.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5,
        ) as detector:
            results = detector.process(rgb_array)
            if results.detections:
                h, w = rgb_array.shape[:2]
                for det in results.detections:
                    bbox = det.location_data.relative_bounding_box
                    fx = max(0, int(bbox.xmin * w))
                    fy = max(0, int(bbox.ymin * h))
                    fw = min(int(bbox.width * w), w - fx)
                    fh = min(int(bbox.height * h), h - fy)

                    kps = det.location_data.relative_keypoints
                    left_eye = right_eye = nose = mouth = None
                    if len(kps) >= 6:
                        right_eye = (int(kps[0].x * w), int(kps[0].y * h))
                        left_eye = (int(kps[1].x * w), int(kps[1].y * h))
                        nose = (int(kps[2].x * w), int(kps[2].y * h))
                        mouth = (int(kps[3].x * w), int(kps[3].y * h))

                    faces.append(FaceBox(
                        x=fx, y=fy, width=fw, height=fh,
                        confidence=det.score[0] if det.score else 0.8,
                        left_eye=left_eye, right_eye=right_eye,
                        nose=nose, mouth=mouth,
                    ))
                logger.info("MediaPipe Solutions detected %d face(s)", len(faces))
    except Exception as exc:
        logger.debug("MediaPipe Solutions detection skipped: %s", exc)
    return faces


def _detect_mediapipe(rgb_array: np.ndarray) -> List[FaceBox]:
    """Detect faces using MediaPipe (Tasks API first, then legacy Solutions)."""
    faces = _detect_mediapipe_tasks(rgb_array)
    if not faces:
        faces = _detect_mediapipe_solutions(rgb_array)
    return faces


def _detect_opencv(gray_array: np.ndarray) -> List[FaceBox]:
    """Detect faces using OpenCV Haar cascades with eye landmark detection."""
    faces = []
    try:
        # Cascades to try in order of precision
        cascades = [
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
            cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml",
        ]
        
        detections = []
        for c_path in cascades:
            cascade = cv2.CascadeClassifier(c_path)
            if not cascade.empty():
                dets = cascade.detectMultiScale(
                    gray_array,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(60, 60),
                )
                if len(dets) > 0:
                    detections = dets
                    break

        # Eye cascade for landmark extraction
        eye_cascade_path = cv2.data.haarcascades + "haarcascade_eye.xml"
        eye_cascade = cv2.CascadeClassifier(eye_cascade_path)

        for (x, y, w, h) in detections:
            left_eye = right_eye = None
            has_eyes = False
            if not eye_cascade.empty():
                # Search for eyes in upper half of face
                roi_upper = gray_array[y : y + int(h * 0.55), x : x + w]
                eyes = eye_cascade.detectMultiScale(roi_upper, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15))
                if len(eyes) >= 2:
                    # Sort eyes horizontally
                    sorted_eyes = sorted(eyes, key=lambda e: e[0])
                    e1 = sorted_eyes[0]
                    e2 = sorted_eyes[1]
                    left_eye = (int(x + e1[0] + e1[2] // 2), int(y + e1[1] + e1[3] // 2))
                    right_eye = (int(x + e2[0] + e2[2] // 2), int(y + e2[1] + e2[3] // 2))
                    has_eyes = True

            conf = 0.85 if has_eyes else 0.5
            faces.append(FaceBox(
                x=int(x), y=int(y), width=int(w), height=int(h),
                confidence=conf,
                left_eye=left_eye, right_eye=right_eye,
            ))
        logger.info("OpenCV Haar detected %d face(s)", len(faces))
    except Exception as exc:
        logger.warning("OpenCV face detection failed: %s", exc)
    return faces


def detect_face(image: Image.Image) -> Tuple[FaceBox, List[str]]:
    """Detect the largest face in the image.

    Tries MediaPipe first, falls back to OpenCV Haar cascade.

    Args:
        image: PIL Image (RGB).

    Returns:
        Tuple of (largest FaceBox, list of warning messages).

    Raises:
        NoFaceFoundError: If no face is detected.
    """
    warnings = []
    rgb_array = np.array(image.convert("RGB"))

    # Try MediaPipe first
    faces = _detect_mediapipe(rgb_array)

    # Fallback to OpenCV
    if not faces:
        logger.info("MediaPipe found no faces, trying OpenCV Haar cascade")
        gray = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
        faces = _detect_opencv(gray)

    if not faces:
        raise NoFaceFoundError()

    # Score and rank candidates: prioritize confirmed eyes, confidence, and size
    def score_face(f: FaceBox) -> float:
        eye_bonus = 1.5 if (f.left_eye and f.right_eye) else 1.0
        return (f.width * f.height) * f.confidence * eye_bonus

    faces.sort(key=score_face, reverse=True)
    best = faces[0]

    # Only warn about multiple faces if secondary candidates are significant
    if len(faces) > 1:
        best_area = best.width * best.height
        significant_faces = [
            f for f in faces
            if (f.width * f.height) >= 0.35 * best_area
        ]
        if len(significant_faces) > 1:
            msg = f"Multiple faces found ({len(significant_faces)}). Using the largest one."
            warnings.append(msg)
            logger.warning(msg)

    return best, warnings


# ---------------------------------------------------------------------------
# Head bounds from alpha mask
# ---------------------------------------------------------------------------

def _find_head_top(alpha: np.ndarray, face: FaceBox) -> int:
    """Find the real top of the head (including hair) from the alpha mask.

    Looks upward from the face box top within the face's horizontal span.
    """
    # Search column range: the face horizontal region, slightly expanded
    left = max(0, face.x - face.width // 4)
    right = min(alpha.shape[1], face.x + face.width + face.width // 4)

    # Scan upward from face top
    for row in range(face.y, -1, -1):
        row_slice = alpha[row, left:right]
        if np.max(row_slice) < 30:  # Mostly transparent
            return row + 1
    return 0  # Top of image


def _find_chin(face: FaceBox) -> int:
    """Estimate chin position from face box."""
    # Chin is roughly at the bottom of the face box, slightly below
    return face.y + face.height


# ---------------------------------------------------------------------------
# Rotation correction
# ---------------------------------------------------------------------------

def _auto_rotate(image: Image.Image, face: FaceBox) -> Tuple[Image.Image, FaceBox]:
    """Auto-rotate image to level the eyes (if eye landmarks available)."""
    if face.left_eye is None or face.right_eye is None:
        return image, face

    dx = face.right_eye[0] - face.left_eye[0]
    dy = face.right_eye[1] - face.left_eye[1]
    angle = math.degrees(math.atan2(dy, dx))

    # Only correct if the tilt is noticeable but not extreme
    if abs(angle) < 1.0 or abs(angle) > 30.0:
        return image, face

    logger.info("Auto-rotating by %.1f degrees to level eyes", -angle)

    # Rotate the image around the center of the face
    cx = face.x + face.width // 2
    cy = face.y + face.height // 2

    rotated = image.rotate(-angle, center=(cx, cy), resample=Image.BICUBIC, expand=False)

    # Approximate the face box in the rotated image (small angle, so close enough)
    # For better accuracy we'd re-detect, but this is good enough for small tilts
    return rotated, face


# ---------------------------------------------------------------------------
# Passport crop
# ---------------------------------------------------------------------------

def crop_passport(
    image: Image.Image,
    face: FaceBox,
    alpha_mask: Optional[Image.Image],
    photo_w_mm: float,
    photo_h_mm: float,
    dpi: int = 300,
    head_ratio: float = 0.75,
    bg_color: str = "#FFFFFF",
) -> Image.Image:
    """Crop and resize image to exact passport photo dimensions.

    The head (top of hair to chin) takes head_ratio of the photo height,
    centered horizontally on the face.

    Args:
        image: Source image (RGB or RGBA).
        face: Detected face box.
        alpha_mask: Alpha channel from background removal (for finding hair top).
        photo_w_mm: Output width in millimeters.
        photo_h_mm: Output height in millimeters.
        dpi: Output resolution.
        head_ratio: Fraction of photo height the head should occupy.
        bg_color: Background color hex for padding.

    Returns:
        Cropped and resized image at exact pixel dimensions.
    """
    # Auto-rotate if tilted
    image, face = _auto_rotate(image, face)

    # Output pixel dimensions
    out_w = round(photo_w_mm / 25.4 * dpi)
    out_h = round(photo_h_mm / 25.4 * dpi)
    aspect = out_w / out_h

    # Find head bounds
    if alpha_mask is not None:
        alpha_arr = np.array(alpha_mask.convert("L"))
        head_top = _find_head_top(alpha_arr, face)
    else:
        # Estimate: top of head is roughly 40% above face box top
        head_top = max(0, face.y - int(face.height * 0.4))

    chin = _find_chin(face)
    head_height = max(chin - head_top, face.height)

    # The crop height: head should be head_ratio of the total
    crop_h = int(head_height / head_ratio)

    # The crop width from aspect ratio
    crop_w = int(crop_h * aspect)

    # Position the crop: head centered vertically in the top head_ratio portion
    # Top margin = small space above head
    top_margin_ratio = (1.0 - head_ratio) * 0.3  # 30% of remaining space above head
    crop_top = head_top - int(crop_h * top_margin_ratio)

    # Center horizontally on the face center
    face_cx = face.x + face.width // 2
    crop_left = face_cx - crop_w // 2

    # Ensure we don't go negative or past the image
    img_w, img_h = image.size

    # Create the crop region (may extend beyond image bounds)
    crop_box = (crop_left, crop_top, crop_left + crop_w, crop_top + crop_h)

    # Pad if crop extends beyond image
    pad_left = max(0, -crop_box[0])
    pad_top = max(0, -crop_box[1])
    pad_right = max(0, crop_box[2] - img_w)
    pad_bottom = max(0, crop_box[3] - img_h)

    # Adjust crop to image bounds
    actual_left = max(0, crop_box[0])
    actual_top = max(0, crop_box[1])
    actual_right = min(img_w, crop_box[2])
    actual_bottom = min(img_h, crop_box[3])

    # Crop the available region
    cropped = image.crop((actual_left, actual_top, actual_right, actual_bottom))

    # Parse background color for padding
    hex_c = bg_color.lstrip("#")
    if len(hex_c) == 3:
        hex_c = "".join(c * 2 for c in hex_c)
    bg_rgb = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16))

    # If padding needed, place crop on a larger canvas
    if pad_left > 0 or pad_top > 0 or pad_right > 0 or pad_bottom > 0:
        if image.mode == "RGBA":
            padded = Image.new("RGBA", (crop_w, crop_h), bg_rgb + (255,))
        else:
            padded = Image.new("RGB", (crop_w, crop_h), bg_rgb)
        padded.paste(cropped, (pad_left, pad_top))
        cropped = padded

    # Resize to exact output dimensions with high quality
    result = cropped.resize((out_w, out_h), Image.LANCZOS)

    return result
