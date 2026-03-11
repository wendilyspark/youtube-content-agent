# YouTube Agent

A multi-agent pipeline for researching and producing YouTube videos end-to-end.
Scans competitor videos → Claude analysis → research brief → script → visual direction → AI images + voiceover → final MP4.

All intermediate outputs sync to Google Sheets for human review and editing before each production step.

---

## Installing as a Claude Code Skill

This tool is designed to run inside [Claude Code](https://claude.ai/claude-code) as a skill — Claude guides you through the entire pipeline conversationally.

**1. Clone into your Claude skills directory**

```bash
git clone https://github.com/your-username/youtube-content-agent ~/.claude/skills/youtube-agent
cd ~/.claude/skills/youtube-agent
```

**2. Install system dependencies**

```bash
# macOS
brew install ffmpeg python@3.11

# Ubuntu / Debian
sudo apt install ffmpeg python3.11
```

**3. Install Python packages**

```bash
pip install -r requirements.txt
```

**4. Set up your API keys**

```bash
cp .env.example .env
# Open .env and fill in your keys — see the Setup section below
```

**5. Add your Google service account**

Download your `service_account.json` from Google Cloud and place it in the `youtube-agent/` directory (see [Step 6](#step-6--google-sheets-script-review) below).

**6. Verify all connections**

```bash
python verify_apis.py
```

You should see ✓ next to all 5 services before proceeding.

**7. Start Claude Code and ask it to make a video**

Open Claude Code from the `youtube-agent/` directory and say:
> *"I want to make a YouTube video about [your topic]"*

Claude will guide you through the full pipeline step by step.

---

## What it produces

```
output/projects/{title}_{timestamp}/
├── images/   scene_01.jpg … scene_09.jpg   ← Stability AI, 16:9
├── audio/    scene_01.mp3 … scene_09.mp3   ← ElevenLabs voiceover
└── {title}.mp4                              ← assembled video
```

Images and audio can also be imported directly into CapCut or iMovie if you prefer to edit manually.

---

## API Accounts Required

5 accounts are needed. Most have free tiers sufficient for testing.

| Service | What it does | Free tier? |
|---------|-------------|------------|
| YouTube Data API v3 | Scans competitor videos | Yes (Google Cloud free quota) |
| Anthropic (Claude) | Research, scripting, analysis | Pay-as-you-go (~$0.10–0.30/video) |
| ElevenLabs | Text-to-speech voiceover | Yes (10k chars/month) |
| Stability AI | AI image generation | Yes (free credits on signup) |
| Google Sheets | Human review & script editing | Free (Google account) |

---

## Setup

### Step 1 — Copy the environment template

```bash
cp .env.example .env
```

Open `.env` and fill in each key. Instructions per service below.

---

### Step 2 — YouTube Data API v3

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → **APIs & Services → Library**
3. Search for **YouTube Data API v3** → Enable it
4. Go to **Credentials → Create Credentials → API Key**
5. Add to `.env`:
   ```
   YOUTUBE_API_KEY=AIzaSy...
   ```

---

### Step 3 — Anthropic API (Claude)

1. Go to [console.anthropic.com](https://console.anthropic.com) → sign up
2. **API Keys → Create Key**
3. Add to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
> Add credits at **Billing**. A full video pipeline costs roughly $0.10–0.30.

---

### Step 4 — ElevenLabs (voiceover)

1. Go to [elevenlabs.io](https://elevenlabs.io) → sign up
2. Profile icon → **Profile → API Key**
3. Add to `.env`:
   ```
   ELEVENLABS_API_KEY=sk_...
   ```
> Free tier: 10,000 characters/month. A 10-minute video uses ~1,500–2,000 characters.

---

### Step 5 — Stability AI (images)

1. Go to [platform.stability.ai](https://platform.stability.ai) → sign up
2. **Account → API Keys → Create API Key**
3. Add to `.env`:
   ```
   STABILITY_API_KEY=sk-...
   ```
> New accounts get free credits. Each image costs ~$0.003. A 9-scene video = ~$0.03.

---

### Step 6 — Google Sheets (script review)

Requires a **service account** — a bot account that can read/write your spreadsheet.

#### 6a. Create the service account

1. Go to [Google Cloud Console](https://console.cloud.google.com) → your project
2. **APIs & Services → Library** → enable **Google Sheets API** and **Google Drive API**
3. **IAM & Admin → Service Accounts → Create Service Account** (name it anything)
4. Click the account → **Keys → Add Key → Create new key → JSON**
5. Rename the downloaded file to `service_account.json`, place it in this directory
6. Add to `.env`:
   ```
   GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
   ```

#### 6b. Create the Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) → create a new spreadsheet
2. Copy the ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/THIS_PART/edit
   ```
3. Add to `.env`:
   ```
   GOOGLE_SHEETS_ID=your_sheet_id_here
   ```

#### 6c. Share the sheet with the service account

1. Open `service_account.json` → find `"client_email"` (looks like `name@project.iam.gserviceaccount.com`)
2. In your Google Sheet: **Share → paste that email → Editor → Send**

---

### Step 7 — Verify everything is connected

```bash
python verify_apis.py
```

All 5 should show ✓. Fix any that show ✗ before running the pipeline.

---

## Quick Start

```bash
# First time: build a style library from competitor videos
python main.py scan --topics jungian
python main.py analyze

# Create a video
python main.py research --topic "the Jungian shadow in relationships"
python main.py write --minutes 10
# ⏸ Review + edit script in Google Sheets → Scripts tab
python main.py direct
python main.py voices           # pick a voice, copy the ID
python main.py produce --voice-id <ID>
```

See `SKILL.md` for the full guided workflow and all available commands.

---

## Optional: Residential Proxy

If YouTube blocks transcript fetching in your region:

1. Sign up at [webshare.io](https://www.webshare.io) → Residential plan
2. **Proxy List → show credentials**
3. Add to `.env`:
   ```
   WEBSHARE_PROXY_URL=http://username:password@proxy.webshare.io:80
   ```

Leave blank to skip (works fine in most regions).

---

## Security

- **Never commit `.env` or `service_account.json`** — both are in `.gitignore`
- If you accidentally expose a key, rotate it immediately at the provider's dashboard
- `cookies.txt` (optional, for transcript fetching) is also gitignored

---

## License

MIT — see [LICENSE](LICENSE)
