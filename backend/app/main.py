from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from datetime import datetime, timezone

from app.models import CommandPayload, TelemetryPayload
from app.store import commands_store, telemetry_store

app = FastAPI(title="ARIS Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@app.get("/api/v1/status/summary")
def get_status_summary():
    total_units = len(telemetry_store)
    online_units = sum(
        1 for item in telemetry_store.values()
        if item["connection_status"] == "online"
    )
    unstable_units = sum(
        1 for item in telemetry_store.values()
        if item["connection_status"] == "unstable"
    )
    offline_units = sum(
        1 for item in telemetry_store.values()
        if item["connection_status"] == "offline"
    )

    avg_latency = 0
    if telemetry_store:
        avg_latency = sum(item["latency_ms"] for item in telemetry_store.values()) / len(telemetry_store)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_units": total_units,
        "online_units": online_units,
        "unstable_units": unstable_units,
        "offline_units": offline_units,
        "avg_latency_ms": round(avg_latency, 2),
        "total_commands": len(commands_store),
    }


@app.get("/api/v1/helmets")
def get_helmets():
    return list(telemetry_store.values())


@app.get("/api/v1/logs")
def get_logs():
    return commands_store[-50:][::-1]


@app.post("/api/v1/commands")
async def receive_command(payload: CommandPayload):
    command_data = payload.model_dump()
    commands_store.append(command_data)

    await manager.broadcast({
        "event": "new_command",
        "data": command_data
    })

    return {
        "message": "Command received successfully",
        "ack": True,
        "received_at": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/v1/telemetry")
async def receive_telemetry(payload: TelemetryPayload):
    telemetry_data = payload.model_dump()
    telemetry_store[payload.device_id] = telemetry_data

    await manager.broadcast({
        "event": "telemetry_update",
        "data": telemetry_data
    })

    return {
        "message": "Telemetry received successfully",
        "ack": True,
        "received_at": datetime.now(timezone.utc).isoformat()
    }


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "event": "welcome",
            "message": "Connected to ARIS dashboard websocket"
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)