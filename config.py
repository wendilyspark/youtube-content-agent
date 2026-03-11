import os
import json
from dotenv import load_dotenv

# Load .env from the same directory as this file
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- API Keys ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY", "")

# --- User-defined topic bundles ---
# Edit topics.json to add or modify topic keyword bundles.
# Each key is a label (e.g. "stoicism", "finance_news", "fitness").
# Each value is a list of search queries used to find relevant videos.
# New topics can also be added interactively via: python main.py scan --topics <new_label>
_TOPICS_FILE = os.path.join(os.path.dirname(__file__), "topics.json")

def load_topics() -> dict:
    if os.path.exists(_TOPICS_FILE):
        with open(_TOPICS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_topics(topics: dict) -> None:
    with open(_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)

TOPICS = load_topics()

# --- Search settings ---
MAX_RESULTS_PER_QUERY = 2       # videos per keyword search
MIN_VIEW_COUNT = 50_000         # filter out low-view videos
PUBLISHED_AFTER_DAYS = 365      # only videos from last N days (None = all time)
PREFERRED_LANGUAGE = "en"       # transcript language preference

# --- Claude model ---
CLAUDE_MODEL = "claude-sonnet-4-6"

# --- Transcript fetch settings ---
# Export cookies from Chrome/Firefox to work around YouTube IP blocks.
# How to export: install "Get cookies.txt LOCALLY" Chrome extension,
# go to youtube.com while logged in, click the extension → Export → save as cookies.txt
# Then set the path here or as env var YOUTUBE_COOKIES_FILE
YOUTUBE_COOKIES_FILE = os.environ.get("YOUTUBE_COOKIES_FILE",
    os.path.join(os.path.dirname(__file__), "cookies.txt"))
TRANSCRIPT_REQUEST_DELAY = 1.5   # seconds between transcript fetches

# --- Google Sheets Export ---
# Create a service account at https://console.cloud.google.com → enable Sheets API
# Download the JSON key and set the path below.
# Share your Google Sheet with the service account email (editor access).
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(os.path.dirname(__file__), "service_account.json"))
GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")

# --- Residential Proxy (WebShare) ---
# Sign up at https://www.webshare.io/ → Residential plan → Proxy List → show credentials
# Format: http://username:password@proxy.webshare.io:80
# Leave blank to disable proxy.
WEBSHARE_PROXY_URL = os.environ.get("WEBSHARE_PROXY_URL", "")

# --- ElevenLabs voice defaults ---
# Default: calm, intelligent, deep — can be overridden at produce time
DEFAULT_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"   # Daniel (deep, calm, authoritative)
DEFAULT_VOICE_MODEL = "eleven_turbo_v2_5"

# --- Stability AI image defaults ---
STABILITY_IMAGE_MODEL = "stable-image/generate/core"  # Stable Image Core (best quality/cost)
IMAGE_STYLE_PRESET = "cinematic"  # cinematic | analog-film | fantasy-art | digital-art | photographic
IMAGE_ASPECT_RATIO = "16:9"       # for YouTube landscape format

# --- Output ---
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(_BASE_DIR, "output")
SCRIPTS_DIR = os.path.join(_BASE_DIR, "output", "scripts")
PROJECTS_DIR = os.path.join(_BASE_DIR, "output", "projects")
