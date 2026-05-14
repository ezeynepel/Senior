"""Temporary model-output bridge for ARIS.

The real recognition model is not ready yet. Until it arrives, this module
produces one structured `modelOutput` object from the latest camera frame.

Later integration point:
    Replace MockModelOutputProvider.generate(...) with a provider that calls
    the real model and returns the same ModelOutput schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from camera_source import CameraFrame


@dataclass(frozen=True)
class ModelOutput:
    """Single structured value consumed by API, WebSocket, and frontend."""

    device_id: str
    timestamp: str
    status: str
    result: str
    label: str
    confidence: float
    source: str
    priority: str
    frame: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseModelOutputProvider:
    """Interface for temporary mock output and future real model output."""

    def generate(self, *, device_id: str, frame: Optional[CameraFrame], camera_online: bool) -> ModelOutput:
        raise NotImplementedError


class MockModelOutputProvider(BaseModelOutputProvider):
    """Temporary static/model-like output provider.

    It intentionally depends on the camera frame metadata, so the dashboard works
    like a real model pipeline even before the actual ML code exists.
    """

    def __init__(self) -> None:
        self._labels = [
            ("NO_COMMAND", "No command detected", "low", 0.62),
            ("HAND_VISIBLE", "Hand/gesture candidate visible", "medium", 0.78),
            ("FACE_VISIBLE", "Face/expression candidate visible", "medium", 0.74),
            ("READY", "Camera input ready for model inference", "low", 0.91),
        ]
        self._index = 0

    def generate(self, *, device_id: str, frame: Optional[CameraFrame], camera_online: bool) -> ModelOutput:
        timestamp = datetime.now(timezone.utc).isoformat()

        if frame is None or not camera_online:
            return ModelOutput(
                device_id=device_id,
                timestamp=timestamp,
                status="offline",
                result="no_frame",
                label="CAMERA_OFFLINE",
                confidence=0.0,
                source="model_output_bridge",
                priority="low",
                frame={
                    "width": 0,
                    "height": 0,
                    "fps": 0,
                    "latency_ms": 0,
                    "frames_captured": 0,
                },
                raw={"message": "Camera frame is not available yet."},
            )

        label, result, priority, confidence = self._labels[self._index % len(self._labels)]
        self._index += 1

        return ModelOutput(
            device_id=device_id,
            timestamp=timestamp,
            status="processed",
            result=result,
            label=label,
            confidence=confidence,
            source="model_output_bridge",
            priority=priority,
            frame={
                "width": frame.width,
                "height": frame.height,
                "fps": frame.fps,
                "latency_ms": frame.latency_ms,
                "frames_captured": frame.frame_count,
            },
            raw={
                "temporary": True,
                "integration_note": "Replace MockModelOutputProvider with the real model provider later.",
            },
        )
