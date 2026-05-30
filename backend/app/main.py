from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

DEVICE_ID = "helmet_01"

app = FastAPI(title="ARIS Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_dashboards: set[WebSocket] = set()
event_log: list[dict[str, Any]] = []

latest_frame: bytes | None = None


async def broadcast(event: dict[str, Any]) -> None:
    disconnected = []

    for websocket in connected_dashboards:
        try:
            await websocket.send_json(event)
        except RuntimeError:
            disconnected.append(websocket)

    for websocket in disconnected:
        connected_dashboards.discard(websocket)


@app.get("/api/v1/status/summary")
def get_status_summary():
    return {
        "total_units": 1,
        "online_units": 1,
        "avg_latency_ms": 0,
        "total_commands": len(event_log),
    }


@app.get("/api/v1/helmets")
def get_helmets():
    return [
        {
            "device_id": DEVICE_ID,
            "connection_status": "online",
        }
    ]

@app.get("/api/v1/helmets/{device_id}")
def get_helmet_detail(device_id: str):

    commands = [
        cmd for cmd in event_log
        if cmd.get("device_id") == device_id
    ]

    return {
        "device_id": device_id,
        "telemetry": {
            "connection_status": "online",
            "battery_level": 100,
            "signal_strength": 100,
            "latency_ms": 0,
            "temperature_c": 0
        },
        "total_commands": len(commands),
        "high_priority_count": sum(
            1 for cmd in commands
            if cmd.get("priority") == "high"
        )
    }


@app.get("/api/v1/logs")
def get_logs():
    return event_log


@app.post("/api/v1/commands")
async def receive_command(command: dict[str, Any]):
    if "device_id" not in command:
        command["device_id"] = DEVICE_ID

    event_log.insert(0, command)
    del event_log[100:]

    await broadcast({
        "event": "new_command",
        "data": command
    })

    return {"status": "ok"}


@app.post("/api/v1/camera/upload")
async def upload_camera_frame(frame: bytes = Body(...)):
    global latest_frame
    latest_frame = frame
    return {"status": "frame_received"}


@app.get("/api/v1/camera/frame")
def get_single_frame():
    if latest_frame is None:
        raise HTTPException(
            status_code=503,
            detail="Camera frame is not available yet"
        )

    return StreamingResponse(
        iter([latest_frame]),
        media_type="image/jpeg"
    )


@app.get("/api/v1/camera/stream")
def get_camera_stream():

    async def frame_generator():
        while True:
            if latest_frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + latest_frame
                    + b"\r\n"
                )

            await asyncio.sleep(0.03)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_dashboards.add(websocket)

    await websocket.send_json({
        "event": "connected",
        "data": {"status": "ok"}
    })

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_dashboards.discard(websocket)