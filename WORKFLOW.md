# YouTube Agent — Workflow Reference Document

> **Purpose:** This document fully describes the YouTube content research and video production pipeline.
> Load this document at the start of any session to resume without re-explaining any steps.
> Treat each numbered step as a node in the workflow graph — inputs, outputs, model/API, and storage are all specified.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 1 — STYLE LIBRARY (run once per niche)            │
└─────────────────────────────────────────────────────────────────────────────┘

  [TRIGGER: User]
       │
       ▼
┌──────────────┐     YouTube Data API v3      ┌─────────────────────────────┐
│   STEP 1     │ ──────────────────────────►  │  OUTPUT: video metadata     │
│   SCAN       │   query / channel / URL       │  scan_{label}_{ts}.json     │
│  scanner.py  │                               │  output/ directory          │
└──────────────┘                               └─────────────┬───────────────┘
                                                             │
       ▼
┌──────────────┐   youtube-transcript-api     ┌─────────────────────────────┐
│   STEP 2     │   + yt-dlp (fallback)        │  OUTPUT: transcript text    │
│  TRANSCRIPT  │ ──────────────────────────►  │  analysis_{label}_{ts}.json │
│ transcript.py│   video_id → raw text        │  (transcript_data field)    │
└──────────────┘                               └─────────────┬───────────────┘
                                                             │
       ▼
┌──────────────┐   Claude Sonnet 4.6          ┌─────────────────────────────┐
│   STEP 3     │   max_tokens: 4096           │  OUTPUT: structured         │
│   ANALYZE    │ ──────────────────────────►  │  style analysis per video   │
│  analyzer.py │   transcript → JSON          │  analysis_{label}_{ts}.json │
└──────────────┘   (hook_style, tone, voice,  │  (analysis field)           │
                    pacing, rhetorical devices │                             │
                    topics, engagement factors)│  → Google Sheets:           │
                                               │  Tab "Research Library"     │
                                               └─────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 2 — CONTENT CREATION (per video)                  │
└─────────────────────────────────────────────────────────────────────────────┘

  [TRIGGER: User provides topic + angle]
       │
       ▼
┌──────────────┐   Claude Sonnet 4.6          ┌─────────────────────────────┐
│   STEP 4     │   max_tokens: 8192           │  OUTPUT: content brief      │
│  RESEARCH    │ ──────────────────────────►  │  brief_{ts}.json            │
│  research.py │   topic + angle → JSON       │  output/scripts/ directory  │
└──────────────┘   (hook_angles, key_concepts,│                             │
                    narrative_arc, sections,   │  → Google Sheets:           │
                    supporting_material,       │  Tab "Research Brief"       │
                    seo_keywords)              │  Tab "Topic Ideas"          │
                                               └─────────────────────────────┘
       │
       ▼                                         ⏸ CHECKPOINT (optional)
┌──────────────┐   Claude Sonnet 4.6          ┌─────────────────────────────┐
│   STEP 5     │   max_tokens: 8192           │  OUTPUT: script draft       │
│    WRITE     │ ──────────────────────────►  │  draft_{ts}.json            │
│   writer.py  │   brief + style_analyses     │  output/scripts/ directory  │
└──────────────┘   → JSON (scenes array:      │                             │
                    scene_number, label,       │  → Google Sheets:           │
                    script, image_prompt,      │  Tab "Scripts"              │
                    timestamp_estimate)        │  (Writer columns only)      │
                                               └─────────────────────────────┘
       │
       │   ⏸ HUMAN REVIEW CHECKPOINT
       │   User reviews draft in Google Sheets "Scripts" tab
       │   Edits script text / image prompts directly in Sheets
       │   Run: python main.py pull-script --number N  (syncs edits back to JSON)
       │
       ▼
┌──────────────┐   Claude Sonnet 4.6          ┌─────────────────────────────┐
│   STEP 6     │   max_tokens: 8192           │  OUTPUT: directed script    │
│   DIRECT     │ ──────────────────────────►  │  directed_{ts}.json         │
│  director.py │   script → enriched JSON     │  output/scripts/ directory  │
└──────────────┘   adds per scene:            │                             │
                    image_prompt (refined),    │  → Google Sheets:           │
                    image_negative_prompt,     │  Tab "Scripts"              │
                    color_palette, mood,       │  (Director columns filled)  │
                    pacing_note, onscreen_text,│                             │
                    visual_throughline,        │                             │
                    color_story                │                             │
                                               └─────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 3 — PRODUCTION (per video)                        │
└─────────────────────────────────────────────────────────────────────────────┘

  [TRIGGER: User selects voice]
       │
       ▼
┌──────────────┐   ElevenLabs API             ┌─────────────────────────────┐
│   STEP 7     │   GET /v1/voices             │  OUTPUT: interactive list   │
│    VOICES    │ ──────────────────────────►  │  of curated voices with     │
│   voices.py  │   → voice list + demos       │  demo audio playback        │
└──────────────┘                               │                             │
                                               │  User picks voice ID        │
                                               └─────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│   STEP 8 — PRODUCE    (media.py)                                             │
│                                                                              │
│  Input: directed_{ts}.json + voice_id                                        │
│                                                                              │
│  ┌─────────────────┐    Stability AI API         ┌────────────────────────┐ │
│  │  8a. IMAGES     │    stable-image/generate/   │ scene_XX.jpg (16:9)    │ │
│  │                 │ ──────────────────────────► │ output/projects/       │ │
│  │  per scene:     │    multipart/form-data      │ {title}_{ts}/images/   │ │
│  │  image_prompt   │    aspect_ratio: 16:9        └────────────────────────┘ │
│  │  + neg_prompt   │    output_format: jpeg                                  │
│  └─────────────────┘    style: cinematic                                     │
│                                                                              │
│  ┌─────────────────┐    ElevenLabs API            ┌────────────────────────┐ │
│  │  8b. VOICEOVER  │    POST /v1/tts/{id}/        │ scene_XX.mp3           │ │
│  │  + TIMESTAMPS   │    with-timestamps        ── │ scene_XX_timestamps    │ │
│  │                 │ ──────────────────────────►  │ .json                  │ │
│  │  per scene:     │    model: eleven_turbo_v2_5  │ output/projects/       │ │
│  │  script text    │    stability: 0.6            │ {title}_{ts}/audio/    │ │
│  └─────────────────┘    similarity_boost: 0.8     └────────────────────────┘ │
│                         style: 0.2                                           │
│                         → audio_base64 + word timestamps                    │
│                                                                              │
│  ┌─────────────────┐    Pillow + ffmpeg pipe       ┌────────────────────────┐ │
│  │  8c. ASSEMBLE   │    OR manual editing         │ final_video.mp4        │ │
│  │  (optional)     │ ──────────────────────────►  │ output/projects/       │ │
│  │                 │    image + audio + captions  │ {title}_{ts}/          │ │
│  │  Ken Burns zoom │    Ken Burns: 1.0→1.25x      │                        │ │
│  │  word captions  │    captions: punctuation-    └────────────────────────┘ │
│  │  (bold white,   │    split, bold white +                                  │
│  │  thick stroke)  │    12-dir stroke outline                                │
│  └─────────────────┘    fps: 25, codec: libx264                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

       │
       ▼
  [END — Assets ready for upload / manual edit / publish]
```

---

## Step-by-Step Command Reference

| Step | Command | Key Flags | Output |
|------|---------|-----------|--------|
| 1. Scan | `python main.py scan` | `--query TEXT` `--label NAME` `--channel URL` `--video URL` `--topics jungian` | `output/scan_{label}_{ts}.json` |
| 2+3. Analyze | `python main.py analyze` | `--label NAME` (omit = all labels) | `output/analysis_{label}_{ts}.json` + Sheets |
| 4. Research | `python main.py research` | `--topic "TEXT"` `--angle "TEXT"` `--niche "TEXT"` | `output/scripts/brief_{ts}.json` + Sheets |
| 5. Write | `python main.py write` | `--brief PATH` `--minutes 10` `--voice-style "second-person"` `--tone "calm"` | `output/scripts/draft_{ts}.json` + Sheets |
| 6. Direct | `python main.py direct` | `--script PATH` (omit = latest draft) | `output/scripts/directed_{ts}.json` + Sheets |
| 7. Voices | `python main.py voices` | _(interactive)_ | voice ID printed to console |
| 8. Produce | `python main.py produce` | `--script PATH` `--voice-id ID` `--project-dir PATH` (resume) | `output/projects/{title}_{ts}/` |
| Sync edits | `python main.py pull-script` | `--number N` | `output/scripts/pulled_scriptN_{ts}.json` |
| List files | `python main.py list` | | console |
| Verify APIs | `python main.py verify_apis.py` | | console |

---

## Human-in-the-Loop Checkpoints

```
Step 3 complete  →  Review "Research Library" tab in Sheets
                    Confirm style data looks correct before writing

Step 5 complete  →  ⏸ MAIN REVIEW GATE
                    Edit script text + image prompts directly in Google Sheets "Scripts" tab
                    Run: python main.py pull-script --number N
                    This syncs your edits back to a local JSON for directing/production

Step 6 complete  →  Review shot list printed to console
                    Check Director image prompts, moods, pacing notes in Sheets

Step 7 complete  →  Listen to ElevenLabs voice demos
                    Select voice ID for each video

Step 8a complete →  (Optional) Review generated images before committing to voiceover
```

---

## Google Sheets Structure

**Spreadsheet ID:** `1uIpqCFGb7c3qSoN1lWQtYn3jCSErl6MOjujA5Z0N464`

| Tab | Populated by | Key Columns |
|-----|-------------|-------------|
| **Topic Ideas** | `research` command | Date, Topic Title, Prompt, Style, Tone, Hooks, Status |
| **Research Library** | `analyze` command | Label, Video Title, Channel, URL, Views, Hook Style, Tone, Narrative Voice, Topics, Main Points, Content Gaps |
| **Research Brief** | `research` command | Topic, Angle, Hook Angles, Key Concepts, Narrative Arc, Sections, Supporting Material |
| **Scripts** | `write` + `direct` commands | Script #, Scene #, Scene Label, Script Text, Writer Image Prompt, Director Image Prompt, Director Negative Prompt, Color Palette, Mood, Pacing Note, On-Screen Text, Visual Throughline, Color Story |

**Deduplication:** Research Library skips rows where URL already exists.
**Edit flow:** Edit any cell in Scripts tab → run `pull-script` → JSON rebuilt with your changes.

---

## Output Directory Structure

```
output/
├── scan_{label}_{ts}.json            ← raw YouTube metadata
├── analysis_{label}_{ts}.json        ← transcripts + Claude analysis
└── scripts/
    ├── brief_{ts}.json               ← research brief (Step 4)
    ├── draft_{ts}.json               ← writer script (Step 5)
    ├── directed_{ts}.json            ← directed script (Step 6)
    └── pulled_scriptN_{ts}.json      ← Sheets-edited version (pull-script)

output/projects/{title}_{ts}/
├── directed_script.json              ← copy of input script
├── images/
│   ├── scene_01.jpg                  ← Stability AI 16:9 JPEG
│   └── scene_XX.jpg
└── audio/
    ├── scene_01.mp3                  ← ElevenLabs voiceover
    ├── scene_01_timestamps.json      ← word-level timestamps (for captions)
    └── scene_XX.mp3 / .json
```

---

## API Configuration

| API | Purpose | Key Config |
|-----|---------|------------|
| **YouTube Data API v3** | Video search, channel scan, metadata | `YOUTUBE_API_KEY` |
| **Anthropic Claude Sonnet 4.6** | Analysis, research, writing, directing | `ANTHROPIC_API_KEY` · Model: `claude-sonnet-4-6` |
| **ElevenLabs** | Voiceover + word timestamps | `ELEVENLABS_API_KEY` · Model: `eleven_turbo_v2_5` |
| **Stability AI** | Scene images | `STABILITY_API_KEY` · Model: `stable-image/generate/core` · 16:9 JPEG |
| **Google Sheets** | All data persistence + human review | `GOOGLE_SHEETS_ID` · `GOOGLE_SERVICE_ACCOUNT_FILE` |

**Verify all APIs:** `python verify_apis.py`

---

## Key Configuration Values (`config.py`)

| Setting | Value | Notes |
|---------|-------|-------|
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | All 4 AI steps use this |
| `MAX_RESULTS_PER_QUERY` | `2` | Videos per keyword search |
| `MIN_VIEW_COUNT` | `50,000` | Filter low-view videos |
| `DEFAULT_VOICE_ID` | `onwK4e9ZLuTAKqWW03F9` | Daniel (deep, calm) |
| `DEFAULT_VOICE_MODEL` | `eleven_turbo_v2_5` | |
| `STABILITY_IMAGE_MODEL` | `stable-image/generate/core` | |
| `IMAGE_STYLE_PRESET` | `cinematic` | Used in Director prompt |
| `IMAGE_ASPECT_RATIO` | `16:9` | YouTube landscape |
| `IMAGE_STYLE_PRESET` | `cinematic` | Default Stability AI style |

---

## Voice Selections (Current Videos)

| Video | Script File | Topic | Voice | Voice ID |
|-------|-------------|-------|-------|----------|
| 1 | `directed_20260302_214320.json` | Subconscious Mind | Daniel | `onwK4e9ZLuTAKqWW03F9` |
| 2 | `directed_20260302_214310.json` | The Void Phase | Daniel | `onwK4e9ZLuTAKqWW03F9` |
| 3 | `directed_20260302_214342.json` | Unprocessed Shadows | Chris | `iP95p4xoKVk53GoZ742B` |

---

## Production Notes & Known Issues

| Issue | Fix Applied |
|-------|-------------|
| Stability AI 400 error | Use `files=` (multipart/form-data), not `data=` |
| [PAUSE] read aloud by ElevenLabs | Replace with `...` before TTS call — already applied in `generate_all_voiceovers()` |
| BrokenPipeError (ffmpeg + concat) | Pre-concatenate audio files to a temp file first, then pipe video frames separately |
| ffmpeg subtitles/drawtext unavailable | This build lacks libass/freetype; use Pillow to render caption text onto frames instead |
| Claude JSON truncation | `max_tokens`: analyzer=4096, all others=8192; strip code fences with regex |
| Sheets 429 rate limit | Director export uses `batch_update()` — all cells in one API call |
| Service account Drive upload | Service accounts have no Drive quota; use AirDrop/iCloud/Downloads folder instead |
| Resume broken production | `--project-dir PATH` auto-loads `directed_script.json` from inside the folder; timestamps saved as `scene_XX_timestamps.json` |
| YouTube transcript blocked | IP blocking on YouTube; transcripts work for pre-saved data (jungian, past_life labels) |

---

## Typical Full Session Flow

```
# ── One-time style library setup ─────────────────────────────────────────────
python main.py scan --topics jungian past_life
python main.py analyze

# ── Per video (repeat for each topic) ────────────────────────────────────────
python main.py research --topic "your topic" --angle "your angle"
python main.py write --minutes 10 --voice-style "second-person (you)" --tone "calm, intelligent"

# ⏸ Open Google Sheets → Scripts tab → review/edit script text & image prompts
python main.py pull-script --number N        # if you made edits

python main.py direct --script output/scripts/draft_{ts}.json
python main.py voices                        # pick voice, copy ID

# ── Production ────────────────────────────────────────────────────────────────
python main.py produce --script output/scripts/directed_{ts}.json --voice-id <ID>

# If interrupted, resume with:
python main.py produce --script output/scripts/directed_{ts}.json \
  --voice-id <ID> \
  --project-dir output/projects/{existing_folder}

# ── Assets for manual video editing ──────────────────────────────────────────
# Images: output/projects/{title}_{ts}/images/scene_XX.jpg
# Audio:  output/projects/{title}_{ts}/audio/scene_XX.mp3
# Copy to Downloads / AirDrop to phone / drag into CapCut
```

---

## File Map

| File | Role |
|------|------|
| `main.py` | CLI orchestrator — all commands route through here |
| `config.py` | All settings + API keys (loaded from `.env`) |
| `scanner.py` | Step 1 — YouTube search, channel scan, URL fetch |
| `transcript.py` | Step 2 — transcript fetching via youtube-transcript-api + yt-dlp |
| `analyzer.py` | Step 3 — Claude analysis of transcripts |
| `research.py` | Step 4 — Claude research brief generation |
| `writer.py` | Step 5 — Claude script writing |
| `director.py` | Step 6 — Claude visual direction |
| `voices.py` | Step 7 — ElevenLabs voice picker |
| `media.py` | Step 8 — Stability AI images + ElevenLabs audio + Pillow/ffmpeg assembly |
| `sheets.py` | Google Sheets export/import for all steps |
| `storage.py` | Local JSON read/write helpers |
| `verify_apis.py` | One-shot check of all 5 API connections |
| `drive_upload.py` | Google Drive folder upload (requires user-owned folder shared with service account) |
| `.env` | API keys (never commit) |
| `service_account.json` | Google service account credentials (never commit) |
