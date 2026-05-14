"""ARIS backend using a real local webcam as the data source.

Run with:
    uvicorn main:app --reload

The frontend keeps using the same dashboard endpoints, but the returned data is
now derived from the live camera source instead of fake/mock payloads.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.app.camera_source import BaseCameraSource, LocalWebcamSource
from model_output import BaseModelOutputProvider, MockModelOutputProvider, ModelOutput

DEVICE_ID = "local_camera_01"

app = FastAPI(title="ARIS Camera Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace this object later with another class implementing BaseCameraSource.
camera_source: BaseCameraSource = LocalWebcamSource(camera_index=0)

# Replace only this provider when the real model code arrives.
model_provider: BaseModelOutputProvider = MockModelOutputProvider()

connected_dashboards: set[WebSocket] = set()

# Feed log generated only from the single structured modelOutput value.
event_log: list[dict[str, Any]] = []
latest_model_output: ModelOutput | None = None


def build_model_output() -> dict[str, Any]:
    """Return the single structured modelOutput value used by the UI.

    The camera remains the input source. For now, MockModelOutputProvider fills
    this object. Later, the real model should return the same schema here.
    """
    global latest_model_output

    frame = camera_source.get_latest_frame()
    latest_model_output = model_provider.generate(
        device_id=DEVICE_ID,
        frame=frame,
        camera_online=camera_source.is_online(),
    )
    return latest_model_output.to_dict()


def get_current_model_output() -> dict[str, Any]:
    """Return cached modelOutput, creating it once if needed."""
    if latest_model_output is None:
        return build_model_output()
    return latest_model_output.to_dict()


def build_camera_telemetry(model_output: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build dashboard telemetry from modelOutput instead of fake API data."""
    output = model_output or get_current_model_output()
    frame = output.get("frame", {})
    is_online = output.get("status") != "offline"

    return {
        "device_id": output["device_id"],
        "timestamp": output["timestamp"],
        "connection_status": "online" if is_online else "offline",
        "source": output["source"],
        "label": output["label"],
        "result": output["result"],
        "confidence": output["confidence"],
        "frame_width": frame.get("width", 0),
        "frame_height": frame.get("height", 0),
        "fps": frame.get("fps", 0),
        "latency_ms": frame.get("latency_ms", 0),
        "frames_captured": frame.get("frames_captured", 0),
    }


def append_model_event(model_output: dict[str, Any]) -> dict[str, Any]:
    """Store a live-feed event derived from modelOutput only."""
    frame = model_output.get("frame", {})
    event = {
        "device_id": model_output["device_id"],
        "timestamp": model_output["timestamp"],
        "command_type": model_output["label"],
        "source": model_output["source"],
        "confidence_score": model_output["confidence"],
        "priority": model_output["priority"],
        "status": model_output["status"],
        "result": model_output["result"],
        "frame_width": frame.get("width", 0),
        "frame_height": frame.get("height", 0),
        "fps": frame.get("fps", 0),
        "latency_ms": frame.get("latency_ms", 0),
    }
    event_log.insert(0, event)
    del event_log[100:]
    return event


async def broadcast(event: dict[str, Any]) -> None:
    """Broadcast a dashboard event to all connected WebSocket clients."""
    disconnected: list[WebSocket] = []

    for websocket in connected_dashboards:
        try:
            await websocket.send_json(event)
        except RuntimeError:
            disconnected.append(websocket)

    for websocket in disconnected:
        connected_dashboards.discard(websocket)


@app.on_event("startup")
async def startup() -> None:
    camera_source.start()
    asyncio.create_task(camera_monitor_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    camera_source.stop()


async def camera_monitor_loop() -> None:
    """Periodically publish modelOutput + telemetry to the dashboard."""
    while True:
        model_output = build_model_output()
        telemetry = build_camera_telemetry(model_output)

        await broadcast({"event": "model_output_update", "data": model_output})
        await broadcast({"event": "telemetry_update", "data": telemetry})

        if model_output["status"] != "offline":
            event = append_model_event(model_output)
            await broadcast({"event": "new_command", "data": event})

        await asyncio.sleep(1)


@app.get("/api/v1/model-output")
def get_model_output() -> dict[str, Any]:
    return get_current_model_output()


@app.get("/api/v1/status/summary")
def get_status_summary() -> dict[str, Any]:
    telemetry = build_camera_telemetry()
    return {
        "total_units": 1,
        "online_units": 1 if telemetry["connection_status"] == "online" else 0,
        "avg_latency_ms": telemetry["latency_ms"],
        "total_commands": len(event_log),
    }


@app.get("/api/v1/helmets")
def get_helmets() -> list[dict[str, Any]]:
    return [build_camera_telemetry()]


@app.get("/api/v1/helmets/{device_id}")
def get_helmet_detail(device_id: str) -> dict[str, Any]:
    if device_id != DEVICE_ID:
        raise HTTPException(status_code=404, detail="Camera device not found")

    telemetry = build_camera_telemetry()
    return {
        "device_id": DEVICE_ID,
        "telemetry": telemetry,
        "total_commands": len(event_log),
        "high_priority_count": sum(1 for item in event_log if item.get("priority") == "high"),
    }


@app.get("/api/v1/logs")
def get_logs() -> list[dict[str, Any]]:
    return event_log


@app.get("/api/v1/camera/frame")
def get_single_frame() -> StreamingResponse:
    frame = camera_source.get_latest_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="Camera frame is not available yet")
    return StreamingResponse(iter([frame.jpeg_bytes]), media_type="image/jpeg")


@app.get("/api/v1/camera/stream")
def get_camera_stream() -> StreamingResponse:
    """MJPEG stream endpoint used by the frontend camera preview."""

    async def frame_generator():
        while True:
            frame = camera_source.get_latest_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame.jpeg_bytes + b"\r\n"
                )
            await asyncio.sleep(0.05)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_dashboards.add(websocket)
    output = get_current_model_output()
    await websocket.send_json({"event": "model_output_update", "data": output})
    await websocket.send_json({"event": "telemetry_update", "data": build_camera_telemetry(output)})

    try:
        while True:
            # Keep the socket alive; the dashboard may send a handshake string.
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_dashboards.discard(websocket)
