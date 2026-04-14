from pydantic import BaseModel
from datetime import datetime
from typing import Literal


class CommandPayload(BaseModel):
    device_id: str
    session_id: str
    timestamp: datetime
    command_type: str
    source: Literal["gesture", "voice", "facial"]
    confidence_score: float
    priority: Literal["low", "medium", "high"]
    status: Literal["validated", "pending"]


class TelemetryPayload(BaseModel):
    device_id: str
    timestamp: datetime
    battery_level: int
    signal_strength: int
    latency_ms: int
    temperature_c: float
    recognition_confidence: float
    connection_status: Literal["online", "offline", "unstable"]