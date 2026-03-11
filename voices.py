"""
Voice Manager: list, preview, and select ElevenLabs voices.
Plays a short demo clip in your terminal so you can hear before choosing.
"""

import os
import json
import tempfile
import subprocess
import requests
from config import ELEVENLABS_API_KEY, DEFAULT_VOICE_ID

BASE_URL = "https://api.elevenlabs.io/v1"
HEADERS = {"xi-api-key": ELEVENLABS_API_KEY}

# Curated voice presets well-suited to calm, intelligent psychology content
CURATED_VOICES = {
    "daniel":   {"id": "onwK4e9ZLuTAKqWW03F9", "desc": "Deep, calm, authoritative British male (DEFAULT)"},
    "adam":     {"id": "pNInz6obpgDQGcFmaJgB", "desc": "Warm, clear, conversational American male"},
    "rachel":   {"id": "21m00Tcm4TlvDq8ikWAM", "desc": "Calm, intelligent, neutral American female"},
    "dorothy":  {"id": "ThT5KcBeYPX3keUQqHPh", "desc": "Pleasant, warm, thoughtful British female"},
    "arnold":   {"id": "VR6AewLTigWG4xSOukaG", "desc": "Deep, commanding, narrative American male"},
    "george":   {"id": "JBFqnCBsd6RMkjVDRZzb", "desc": "Warm, rich, storytelling British male"},
}

DEMO_TEXT = (
    "What if the parts of yourself you've been hiding the most "
    "are actually the source of your greatest power? "
    "Jung called it the Shadow — and today, we're going to explore it."
)


def list_voices(show_all: bool = False) -> list[dict]:
    """
    List available voices.
    show_all=False → only curated presets
    show_all=True  → all voices from your ElevenLabs account
    """
    if not show_all:
        voices = []
        for name, info in CURATED_VOICES.items():
            voices.append({"name": name, "voice_id": info["id"], "description": info["desc"]})
        return voices

    resp = requests.get(f"{BASE_URL}/voices", headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "name": v["name"],
            "voice_id": v["voice_id"],
            "description": v.get("description", ""),
            "labels": v.get("labels", {}),
        }
        for v in data.get("voices", [])
    ]


def generate_demo_audio(voice_id: str, text: str = DEMO_TEXT) -> bytes:
    """Generate a short audio sample for a voice."""
    url = f"{BASE_URL}/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.2},
    }
    resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/json"}, json=payload)
    resp.raise_for_status()
    return resp.content


def play_audio(audio_bytes: bytes) -> None:
    """Play audio bytes using system player (macOS afplay / Linux aplay)."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        if os.uname().sysname == "Darwin":
            subprocess.run(["afplay", tmp_path], check=True)
        else:
            subprocess.run(["aplay", tmp_path], check=True)
    finally:
        os.unlink(tmp_path)


def interactive_voice_picker() -> str:
    """
    Interactive CLI: list voices, play demos on request, return chosen voice_id.
    """
    voices = list_voices(show_all=False)

    print("\n" + "="*60)
    print("VOICE SELECTION")
    print("="*60)
    print(f"Demo text: \"{DEMO_TEXT[:80]}...\"\n")

    for i, v in enumerate(voices, 1):
        default_tag = " ← DEFAULT" if v["voice_id"] == DEFAULT_VOICE_ID else ""
        print(f"  [{i}] {v['name'].upper()}{default_tag}")
        print(f"      {v['description']}")

    print("\nHow to use:")
    print("  Type a number + Enter  → hear a preview")
    print("  Type the same number again → confirm that voice")
    print("  Type 'd' + Enter       → use Daniel (default)")
    print("  Type 'a' + Enter       → list all your ElevenLabs voices\n")

    selected_id = DEFAULT_VOICE_ID
    selected_name = "daniel"
    last_previewed = None

    while True:
        choice = input("Your choice: ").strip().lower()

        if choice == "":
            continue  # ignore accidental empty Enter

        if choice == "d":
            print(f"Using default voice: Daniel")
            return DEFAULT_VOICE_ID

        if choice == "ok" and last_previewed:
            print(f"Selected: {selected_name.upper()}")
            return selected_id

        if choice == "a":
            print("\nFetching all available voices from your account...")
            all_voices = list_voices(show_all=True)
            for j, v in enumerate(all_voices, 1):
                labels = ", ".join(f"{k}:{val}" for k, val in v.get("labels", {}).items())
                print(f"  [{j}] {v['name']} — {labels or v.get('description','')}")
            voices = all_voices
            print()
            continue

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(voices):
                v = voices[idx]
                selected_id = v["voice_id"]
                selected_name = v["name"]

                if last_previewed == selected_id:
                    # Second press of same number = confirm
                    print(f"Selected: {selected_name.upper()}")
                    return selected_id

                print(f"\nPlaying demo for {v['name'].upper()}... (press number again to confirm)")
                try:
                    audio = generate_demo_audio(selected_id)
                    play_audio(audio)
                    last_previewed = selected_id
                    print(f"Press [{choice}] again to confirm, or choose another number.\n")
                except Exception as e:
                    print(f"Could not play audio: {e}")
            else:
                print(f"Invalid choice. Enter 1-{len(voices)}.")
        else:
            print("Invalid input. Enter a number, 'd' for default, or 'ok' to confirm.")
