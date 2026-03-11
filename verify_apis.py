#!/usr/bin/env python3
"""
API Connection Verifier
Runs a lightweight check on each configured API to confirm keys and endpoints are valid.
"""

import sys
import os
import requests
from config import (
    YOUTUBE_API_KEY, ANTHROPIC_API_KEY,
    ELEVENLABS_API_KEY, STABILITY_API_KEY,
    CLAUDE_MODEL, GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_FILE,
)

OK    = "\033[92m✓\033[0m"
FAIL  = "\033[91m✗\033[0m"
WARN  = "\033[93m⚠\033[0m"


def check_youtube():
    print("YouTube Data API v3 ...", end=" ", flush=True)
    if not YOUTUBE_API_KEY:
        print(f"{FAIL} No key set")
        return False
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "id", "id": "dQw4w9WgXcQ", "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"{OK}  Connected")
            return True
        else:
            err = resp.json().get("error", {}).get("message", resp.status_code)
            print(f"{FAIL} {err}")
            return False
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


def check_anthropic():
    print("Anthropic Claude API  ...", end=" ", flush=True)
    if not ANTHROPIC_API_KEY:
        print(f"{FAIL} No key set")
        return False
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8,
            messages=[{"role": "user", "content": "Say OK"}],
        )
        reply = msg.content[0].text.strip()
        print(f"{OK}  Connected  (model: {CLAUDE_MODEL}, reply: '{reply}')")
        return True
    except Exception as e:
        err = str(e)
        if "credit" in err.lower() or "balance" in err.lower():
            print(f"{WARN}  Key valid but low credits — add funds at console.anthropic.com")
        else:
            print(f"{FAIL} {err[:120]}")
        return False


def check_elevenlabs():
    print("ElevenLabs TTS API    ...", end=" ", flush=True)
    if not ELEVENLABS_API_KEY:
        print(f"{FAIL} No key set")
        return False
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            tier = data.get("xi_api_key", {})
            sub = data.get("subscription", {})
            chars_left = sub.get("character_limit", 0) - sub.get("character_count", 0)
            plan = sub.get("tier", "unknown")
            print(f"{OK}  Connected  (plan: {plan}, chars remaining: {chars_left:,})")
            return True
        else:
            err = resp.json().get("detail", {})
            if isinstance(err, dict):
                err = err.get("message", resp.status_code)
            print(f"{FAIL} {err}")
            return False
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


def check_stability():
    print("Stability AI API      ...", end=" ", flush=True)
    if not STABILITY_API_KEY:
        print(f"{FAIL} No key set")
        return False
    try:
        resp = requests.get(
            "https://api.stability.ai/v1/user/account",
            headers={"Authorization": f"Bearer {STABILITY_API_KEY}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            credits = data.get("credits", "?")
            email = data.get("email", "")
            try:
                credits_str = f"{float(credits):.1f}"
            except (TypeError, ValueError):
                credits_str = str(credits)
            print(f"{OK}  Connected  (credits: {credits_str}, account: {email})")
            return True
        else:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            print(f"{FAIL} Status {resp.status_code}: {err}")
            return False
    except Exception as e:
        print(f"{FAIL} {e}")
        return False


def check_sheets():
    print("Google Sheets API     ...", end=" ", flush=True)
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        print(f"{FAIL} GOOGLE_SHEETS_ID or GOOGLE_SERVICE_ACCOUNT_FILE not set")
        return False
    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        print(f"{FAIL} service_account.json not found at: {GOOGLE_SERVICE_ACCOUNT_FILE}")
        return False
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(GOOGLE_SHEETS_ID)
        print(f"{OK}  Connected  (sheet: '{spreadsheet.title}')")
        return True
    except Exception as e:
        err = str(e)
        if "PERMISSION_DENIED" in err or "forbidden" in err.lower():
            print(f"{FAIL} Permission denied — share the sheet with the service account email")
        else:
            print(f"{FAIL} {err[:120]}")
        return False


def main():
    print("\n" + "="*50)
    print("  YouTube Agent — API Connection Check")
    print("="*50 + "\n")

    results = {
        "YouTube":       check_youtube(),
        "Anthropic":     check_anthropic(),
        "ElevenLabs":    check_elevenlabs(),
        "Stability AI":  check_stability(),
        "Google Sheets": check_sheets(),
    }

    print()
    passed = sum(results.values())
    total  = len(results)

    if passed == total:
        print(f"All {total} APIs connected. Ready to run the pipeline.")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"{passed}/{total} APIs OK. Issues with: {', '.join(failed)}")
        print("Fix the above before running produce/voices commands.")
    print()


if __name__ == "__main__":
    main()
