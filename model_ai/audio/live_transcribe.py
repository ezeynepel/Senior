import sounddevice as sd
import soundfile as sf
import subprocess
import os
import time
import sys
import requests
from datetime import datetime, timezone

SAMPLE_RATE = 16000
CHANNELS = 1
DURATION = 5

MIC_DEVICE_INDEX = None

MODEL = "small"
LANGUAGE = "tr"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"

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


def get_priority(confidence):
    if confidence >= 0.80:
        return "high"
    elif confidence >= 0.50:
        return "medium"
    else:
        return "low"


def match_voice_command(text):
    normalized_text = text.lower().strip()

    for spoken_text, command in VOICE_COMMANDS.items():
        if spoken_text in normalized_text:
            return command

    return None


def send_voice_command(command,confidence):

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
        response = requests.post(ARIS_API, json=payload, timeout=1)
        print("ARIS voice command sent:", command, response.status_code)
    except Exception as e:
        print("ARIS backend voice command could not be sent:", e)


def list_input_devices():
    print("\nAvailable microphone/input devices:\n")

    devices = sd.query_devices()

    for i, device in enumerate(devices):
        max_input_channels = device["max_input_channels"]

        if max_input_channels > 0:
            print(f"{i}: {device['name']} | input channels: {max_input_channels}")

    print("\nFind your Bluetooth headset microphone index.")
    print("Then set MIC_DEVICE_INDEX = ... in the code.\n")


def run_whisperx(audio_file):
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
        text=True
    )

    if result.returncode != 0:
        print("\nWhisperX returned an error:")
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


list_input_devices()

print("Live transcription system started...")
print("System will listen and transcribe every 5 seconds.")
print("Press CTRL + C to stop.\n")

counter = 0

while True:
    try:
        base_name = f"temp_{counter}"
        audio_file = base_name + ".wav"

        print("Listening...")

        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            device=MIC_DEVICE_INDEX
        )

        sd.wait()

        sf.write(audio_file, recording, SAMPLE_RATE)

        print("WhisperX is processing...")

        ok = run_whisperx(audio_file)

        txt_file = base_name + ".txt"

        if ok and os.path.exists(txt_file):
            with open(txt_file, "r", encoding="utf-8") as f:
                text = f.read().strip()

            if text:
                print(f"\nARIS Voice Input: {text}\n")

                command = match_voice_command(text)

                if command:
                    send_voice_command(command)
                else:
                    print("No matching ARIS voice command found.\n")
            else:
                print("\nAudio detected, but no text was generated.\n")
        else:
            print("\nTXT file was not generated.\n")

        cleanup_files(base_name)

        counter += 1
        time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nLive transcription system stopped.")
        break

    except Exception as e:
        print(f"\nError occurred: {e}\n")
        time.sleep(1)