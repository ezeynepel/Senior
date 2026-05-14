"""Camera source abstraction for ARIS.

This module keeps the camera implementation isolated from the API layer.
Later, another device/camera can be integrated by implementing the same
BaseCameraSource interface and replacing LocalWebcamSource in main.py.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import cv2


@dataclass(frozen=True)
class CameraFrame:
    """A single encoded camera frame and its metadata."""

    jpeg_bytes: bytes
    timestamp: str
    width: int
    height: int
    latency_ms: int
    fps: float
    frame_count: int


class BaseCameraSource(ABC):
    """Interface that all camera providers must implement."""

    @abstractmethod
    def start(self) -> None:
        """Start the camera capture loop."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the camera capture loop and release resources."""

    @abstractmethod
    def get_latest_frame(self) -> Optional[CameraFrame]:
        """Return the latest encoded frame, if available."""

    @abstractmethod
    def is_online(self) -> bool:
        """Return whether the camera source is currently available."""


class LocalWebcamSource(BaseCameraSource):
    """Local computer webcam implementation using OpenCV VideoCapture."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        jpeg_quality: int = 80,
    ) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.jpeg_quality = jpeg_quality

        self._capture: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[CameraFrame] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._online = False
        self._frame_count = 0

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        if self._capture:
            self._capture.release()
        self._online = False

    def get_latest_frame(self) -> Optional[CameraFrame]:
        with self._lock:
            return self._latest_frame

    def is_online(self) -> bool:
        return self._online

    def _open_capture(self) -> None:
        self._capture = cv2.VideoCapture(self.camera_index)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._online = bool(self._capture.isOpened())

    def _capture_loop(self) -> None:
        self._open_capture()
        last_frame_time = time.perf_counter()

        while self._running:
            if not self._capture or not self._capture.isOpened():
                self._online = False
                time.sleep(1)
                self._open_capture()
                continue

            started_at = time.perf_counter()
            ok, frame = self._capture.read()

            if not ok or frame is None:
                self._online = False
                time.sleep(0.2)
                continue

            self._online = True
            self._frame_count += 1

            height, width = frame.shape[:2]
            now = time.perf_counter()
            elapsed = max(now - last_frame_time, 1e-6)
            fps = round(1.0 / elapsed, 2)
            last_frame_time = now
            latency_ms = int((time.perf_counter() - started_at) * 1000)

            encoded_ok, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
            )
            if not encoded_ok:
                continue

            camera_frame = CameraFrame(
                jpeg_bytes=jpeg.tobytes(),
                timestamp=datetime.now(timezone.utc).isoformat(),
                width=width,
                height=height,
                latency_ms=latency_ms,
                fps=fps,
                frame_count=self._frame_count,
            )

            with self._lock:
                self._latest_frame = camera_frame
