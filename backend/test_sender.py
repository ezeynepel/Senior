import requests
from datetime import datetime, timezone
import random
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"

devices = ["helmet_01", "helmet_02", "helmet_03"]
commands = ["MOVE_FORWARD", "HALT", "REQUEST_BACKUP", "HOLD_POSITION"]
sources = ["gesture", "voice", "facial"]
statuses = ["online", "unstable", "offline"]


def send_telemetry(device_id: str):
    payload = {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "battery_level": random.randint(40, 100),
        "signal_strength": random.randint(45, 100),
        "latency_ms": random.randint(150, 900),
        "temperature_c": round(random.uniform(35.0, 49.0), 1),
        "recognition_confidence": round(random.uniform(0.80, 0.99), 2),
        "connection_status": random.choices(
            statuses, weights=[0.7, 0.2, 0.1], k=1
        )[0]
    }

    requests.post(f"{BASE_URL}/telemetry", json=payload, timeout=5)


def send_command(device_id: str):
    payload = {
        "device_id": device_id,
        "session_id": f"sess_{device_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command_type": random.choice(commands),
        "source": random.choice(sources),
        "confidence_score": round(random.uniform(0.80, 0.99), 2),
        "priority": random.choice(["low", "medium", "high"]),
        "status": "validated"
    }

    requests.post(f"{BASE_URL}/commands", json=payload, timeout=5)


if __name__ == "__main__":
    while True:
        device = random.choice(devices)
        send_telemetry(device)
        send_command(device)
        print(f"Sent telemetry + command for {device}")
        time.sleep(3)