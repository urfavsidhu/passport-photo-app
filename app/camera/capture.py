"""Webcam capture for the Passport Photo App.

Lists available cameras, opens/closes safely, grabs frames,
and provides a QThread-compatible live preview helper.
Works on Windows using cv2.CAP_DSHOW for fast device enumeration.
"""

import logging
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Maximum number of camera indices to probe
_MAX_CAMERA_PROBE = 5


def list_cameras() -> List[Tuple[int, str]]:
    """List available cameras on this system.

    Returns a list of (index, name) tuples. The name is a simple
    description like "Camera 0".
    """
    cameras = []
    # Save the original OpenCV log level and restore it after probing
    try:
        old_level = cv2.getLogLevel()
    except AttributeError:
        old_level = getattr(cv2, "LOG_LEVEL_INFO", 3)

    try:
        cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
    except Exception:
        pass

    try:
        for idx in range(_MAX_CAMERA_PROBE):
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    # Try to read a frame to confirm it really works
                    ret, _ = cap.read()
                    if ret:
                        cameras.append((idx, f"Camera {idx}"))
                    cap.release()
            except Exception as exc:
                logger.debug("Camera probe %d failed: %s", idx, exc)
    finally:
        try:
            cv2.setLogLevel(old_level)
        except Exception:
            pass

    logger.info("Found %d camera(s)", len(cameras))
    return cameras


class CameraCapture:
    """Manage a single camera device.

    Usage:
        cam = CameraCapture(0)
        cam.open()
        frame = cam.grab_frame()
        cam.close()
    """

    def __init__(self, index: int = 0) -> None:
        self._index = index
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open and self._cap is not None and self._cap.isOpened()

    def open(self) -> None:
        """Open the camera. Raises RuntimeError if it fails."""
        if self.is_open:
            return

        try:
            self._cap = cv2.VideoCapture(self._index, cv2.CAP_DSHOW)
        except Exception as exc:
            raise RuntimeError(
                f"Could not open Camera {self._index}.\n"
                f"It may be in use by another application.\n"
                f"Error: {exc}"
            ) from exc

        if not self._cap.isOpened():
            raise RuntimeError(
                f"Camera {self._index} is not available.\n"
                "Make sure it is connected and not in use by another app."
            )

        # Request highest resolution (try 1080p first, then fallback to 720p)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        actual_w = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_w < 1920 or actual_h < 1080:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self._is_open = True
        final_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        final_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("Camera %d opened (%dx%d px)", self._index, final_w, final_h)

    def close(self) -> None:
        """Release the camera."""
        if not self._is_open and self._cap is None:
            return
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as exc:
                logger.debug("Error releasing camera: %s", exc)
            self._cap = None
        self._is_open = False
        logger.info("Camera %d closed", self._index)

    def grab_frame(self) -> Optional[Image.Image]:
        """Grab a single frame and return it as a PIL Image (RGB).

        Returns None if the frame could not be read.
        """
        if not self.is_open:
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            logger.warning("Failed to grab frame from camera %d", self._index)
            return None

        # Convert BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def grab_frame_array(self) -> Optional[np.ndarray]:
        """Grab a single frame as a numpy RGB array.

        Returns None if the frame could not be read.
        """
        if not self.is_open:
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None

        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()
