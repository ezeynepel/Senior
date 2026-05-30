import sounddevice as sd
import soundfile as sf
import subprocess
import os
import time
import sys
import requests
from datetime import datetime, timezone
import imageio_ffmpeg

os.environ["PATH"] = (
    r"C:\Users\DELL\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"
    + os.pathsep +
    os.environ["PATH"]
)

SAMPLE_RATE = 16000
CHANNELS = 1
DURATION = 5

MIC_DEVICE_INDEX = None

#MODEL = "small"
LANGUAGE = "tr"
#DEVICE = "cuda"
#COMPUTE_TYPE = "float16"
MODEL = "tiny"
DURATION = 3
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

ARIS_API = "http://127.0.0.1:8000/api/v1/commands"
DEVICE_ID = "helmet_01"
SESSION_ID = "sess_helmet_01"

VOICE_COMMANDS = {
    "dur": "DUR",
    "ileri": "ILERI",
    "geri": "GERI",
    "sağ": "SAG",
    "sag": "SAG",
    "sol": "SOL",
    "iyi iş": "IYI_IS",
    "iyi is": "IYI_IS"
}


def list_input_devices():
    print("\nAvailable microphone/input devices:\n")

    devices = sd.query_devices()

    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            print(f"{i}: {device['name']} | input channels: {device['max_input_channels']}")

    print("\nIf needed, set MIC_DEVICE_INDEX to the correct microphone index.\n")


def run_whisperx(audio_file):
    ffmpeg_path = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())

    env = os.environ.copy()
    env["PATH"] = ffmpeg_path + os.pathsep + env["PATH"]

    cmd = [
        sys.executable,
        "-m",
        "whisperx",
        audio_file,
        "--model", MODEL,
        "--language", LANGUAGE,
        "--device", DEVICE,
        "--compute_type", COMPUTE_TYPE,
        "--output_format", "txt",
        "--output_dir", "."
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    if result.returncode != 0:
        print("\nWhisperX error:")
        print(result.stderr)
        return False

    return True


def cleanup_files(base_name):
    extensions = [".wav", ".txt", ".json", ".srt", ".vtt", ".tsv", ".aud"]

    for ext in extensions:
        file_path = base_name + ext

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass


def match_voice_command(text):
    normalized_text = text.lower().strip()

    for spoken_text, command in VOICE_COMMANDS.items():
        if spoken_text in normalized_text:
            return command

    return None

def get_priority(confidence):
    if confidence >= 0.80:
        return "high"
    elif confidence >= 0.50:
        return "medium"
    else:
        return "low"

def send_voice_command(command):
    confidence = 0.60
    payload = {
        "device_id": DEVICE_ID,
        "session_id": SESSION_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command_type": command,
        "source": "voice",
        "confidence_score": confidence,
        "priority": get_priority(confidence),
        "status": "validated"
    }

    try:
        response = requests.post(
            ARIS_API,
            json=payload,
            timeout=1
        )

        print("ARIS voice command sent:", command, response.status_code)

    except Exception as e:
        print("ARIS backend voice command could not be sent:", e)


list_input_devices()

print("ARIS live voice recognition started.")
print("System listens every 5 seconds and sends matched commands to dashboard.")
print("Press CTRL + C to stop.\n")

counter = 0

print("ARIS voice demo mode started.")
print("Type: dur, ileri, geri, sağ, sol, iyi iş")
print("Press CTRL + C to stop.\n")

while True:
    try:
        text = input("Voice Input: ").strip()

        if not text:
            continue

        print(f"\nARIS Voice Input: {text}\n")

        command = match_voice_command(text)

        if command:
            send_voice_command(command)
        else:
            print("No matching ARIS voice command found.\n")

    except KeyboardInterrupt:
        print("\nARIS voice demo mode stopped.")
        break