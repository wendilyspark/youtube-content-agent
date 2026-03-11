name: youtube-agent
description: >
  Multi-agent pipeline for YouTube content research and video production.
  Covers the full workflow from scanning competitor videos → Claude analysis →
  research brief → script writing → visual direction → voiceover + image generation → final MP4.
  All intermediate outputs sync to Google Sheets for human review and editing.
  Configurable for any niche or content topic.

---

## Conversational Protocol

When the user asks to research, make, or produce a YouTube video — follow this guided
conversational flow. Ask **one question at a time**. Run commands automatically between
checkpoints. Never dump all commands or options at once.

### Checkpoint 1 — Topic
Ask: **"What topic do you want to make a video about?"**

### Checkpoint 2 — Search directions (if style library doesn't exist)
Check if `output/analysis_*.json` files exist for this niche.
- If analyses **already exist**: skip and say "Using your existing style library."
- If **none exist**: generate 5 sensible search queries from the topic name, then present
  them to the user:

  > "I'll scan YouTube for competitor videos using these search directions:
  > 1. ...
  > 2. ...
  > 3. ...
  > 4. ...
  > 5. ...
  >
  > Scan all of the above, or drop / swap any before I start?"

  Wait for confirmation. Accept "all good", "scan all", or specific changes.
  Then run:
  ```bash
  python3 main.py scan --topics <label> --queries "query 1" "query 2" ...
  python3 main.py analyze
  ```

### Step 3 — Research + confirm direction (lightweight checkpoint)
Run research using only the topic:
```bash
python3 main.py research --topic "..."
```
This exports to Google Sheets (Research Brief tab) automatically.

Show the user a compact summary covering **both** the research output and the style
library patterns observed from scanned videos:

> **Research direction**
> - Proposed title: ...
> - Hook angles: (list 2–3)
> - Narrative arc: problem → journey → resolution (one line each)
>
> **Writing style from your scanned videos**
> - Tone: e.g. calm, reflective, second-person
> - Hook pattern: e.g. opens with a provocative question
> - Narrative voice: e.g. intimate, philosophical

Ask: **"Does this direction and style feel right? Or would you like to adjust — or describe your own style?"**
- "Looks good" → proceed
- They suggest an adjustment → re-run with `--angle "..."`
- They describe their own style → note it and pass to `write` via `--tone` and `--voice-style`

### Checkpoint 4 — Video length
Before asking, show the length range of videos in the style library:
> "The videos I scanned ranged from X to Y minutes (average: Z min)."

Then ask: **"How long should your video be?"** (default: 10 minutes)
Then write the script — derive tone from the style library automatically, do not ask:
```bash
python3 main.py write --minutes N
```

### Checkpoint 5 — Script Review ⏸
The script is exported to Google Sheets (Scripts tab) and the sheet **opens automatically
in the browser** after the write command completes.

Say: "Your script is now open in Google Sheets. Read through each scene, edit anything
that doesn't feel right — then come back and say **'approved'**."
**Wait.** Do not proceed until the user says approved, done, or ready.

### Step 6 — Visual Direction (automatic)
```bash
python3 main.py direct
```

### Checkpoint 7 — Image Style
Open the style picker:
```bash
open style_picker.html
```
Say: "The style picker is open in your browser. Browse the 8 styles and 7 color themes.
Each style card has a **'View more examples'** link to see real AI-generated images in
that style on Lexica. When you've chosen both a style and a color theme, click the
**Copy Settings** button at the bottom of the page — it copies the selection text to
your clipboard. Then paste it here in the chat."

Wait for the user to paste something like: `style=cinematic, theme=dark_mysterious`
Parse the style and theme IDs from that text.

### Checkpoint 8 — Voice
```bash
python3 main.py voices
```
Help the user pick a voice. Note the voice ID.

### Step 9 — Produce (automatic)
```bash
python3 main.py produce --style <style_id> --color-theme <theme_id> --voice-id <ID>
```

This uses the fast **Pillow + ffmpeg renderer** (Ken Burns zoom-in, punctuation-split captions,
bold white text with thick stroke outline). No MoviePy or libass required.

### Checkpoint 10 — Script edits after review (optional)

If the user edits scenes in Google Sheets after reviewing, sync changes back and re-render:

```bash
# 1. Pull edited script from Sheets
python3 main.py pull-script --number 1

# 2. Regenerate audio only for changed scenes (e.g. scenes 1 and 3)
python3 main.py regen-audio \
  --script output/scripts/pulled_script1_<ts>.json \
  --project-dir output/projects/<folder>/ \
  --scenes 1 3 \
  --voice-id <ID>

# 3. Render a preview of affected scenes (auto-opens on macOS)
python3 main.py preview \
  --project-dir output/projects/<folder>/ \
  --scenes 1 2 3 \
  --shadow-color "20,45,55"
```

`--shadow-color` is optional (default black). Pick a dark color that complements the scene's
image tones — e.g. dark teal `20,45,55` for sky-blue scenes, dark amber `45,30,10` for
warm golden scenes.

### Done
Tell the user: "Your assets are ready. Import into CapCut or iMovie:
- **Images:** `output/projects/{title}/images/`
- **Audio:** `output/projects/{title}/audio/`"

---

## Usage

Invoke any step independently. Steps are intentionally decoupled — you control when each advances.

### Full pipeline (typical session)

```bash
# Phase 1 — Build style library (run once per niche)
python main.py scan --topics jungian past_life
python main.py analyze

# Phase 2 — Create content for a new video
python main.py research --topic "your topic" --angle "your angle"
python main.py write --minutes 10 --voice-style "second-person (you)" --tone "calm, intelligent"
# ⏸ Review + edit script in Google Sheets → Scripts tab
python main.py pull-script --number N        # sync edits back if you made any
python main.py direct
python main.py voices                        # interactive — pick a voice, copy ID

# Phase 3 — Produce (uses fast Pillow+ffmpeg renderer)
python main.py produce --script output/scripts/directed_{ts}.json --voice-id <ID>
# Resume interrupted run (automatically loads directed_script.json from project folder):
python main.py produce --voice-id <ID> --project-dir output/projects/{existing_folder}

# Phase 4 — Post-review script edits
python main.py pull-script --number N
python main.py regen-audio \
  --script output/scripts/pulled_scriptN_{ts}.json \
  --project-dir output/projects/{folder} \
  --scenes 1 3 --voice-id <ID>
python main.py preview \
  --project-dir output/projects/{folder} \
  --scenes 1 2 3 --shadow-color "20,45,55"
```

### Scan modes
```bash
python main.py scan --query "Jungian shadow integration" --label shadow_study
python main.py scan --channel https://www.youtube.com/@AcademyOfIdeas --label academy
python main.py scan --video https://youtu.be/ABC123 https://youtu.be/XYZ456
python main.py scan --topics jungian freudian past_life subconscious
```

### Utilities
```bash
python main.py list               # list all saved output files
python verify_apis.py             # check all 5 API connections
python main.py pull-script --number 1 2   # pull specific scripts from Sheets
```

### Full workflow reference
See `WORKFLOW.md` in this directory for the complete pipeline diagram, all API details,
Google Sheets structure, output directory layout, and known issues + fixes.

#requirements

## Python packages (see requirements.txt)
- anthropic
- google-api-python-client
- google-auth
- gspread
- Pillow
- python-dotenv
- requests
- yt-dlp
- youtube-transcript-api

## API keys (set in .env)
- YOUTUBE_API_KEY          — YouTube Data API v3
- ANTHROPIC_API_KEY        — Claude Sonnet 4.6
- ELEVENLABS_API_KEY       — ElevenLabs TTS
- STABILITY_API_KEY        — Stability AI image generation
- GOOGLE_SHEETS_ID         — Target spreadsheet ID
- GOOGLE_SERVICE_ACCOUNT_FILE — Path to service_account.json

## External setup
- Google Cloud project with Sheets API + Drive API enabled
- service_account.json downloaded and placed in this directory
- Google Sheet shared with the service account email (Editor access)

#output

## Per-step outputs

| Step | Output file | Google Sheets tab |
|------|-------------|-------------------|
| scan | `output/scan_{label}_{ts}.json` | — |
| analyze | `output/analysis_{label}_{ts}.json` | Research Library |
| research | `output/scripts/brief_{ts}.json` | Research Brief, Topic Ideas |
| write | `output/scripts/draft_{ts}.json` | Scripts (Writer columns) |
| direct | `output/scripts/directed_{ts}.json` | Scripts (Director columns) |
| produce | `output/projects/{title}_{ts}/` | — |

## Production output structure
```
output/projects/{title}_{ts}/
├── directed_script.json
├── images/scene_01.jpg … scene_XX.jpg   (Stability AI, 16:9)
├── audio/scene_01.mp3 … scene_XX.mp3    (ElevenLabs voiceover)
├── audio/scene_01_timestamps.json …     (word-level caption data)
└── {title}.mp4                          (final video, if assembled)
```

## Manual editing path (alternative to the built-in renderer)
Images + audio from `output/projects/{title}_{ts}/` can be imported directly into
CapCut, iMovie, or any mobile editor. Use the platform's auto-caption feature
instead of the programmatic caption sync.
