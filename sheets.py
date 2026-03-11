"""
Google Sheets Exporter
Syncs pipeline results to a Google Sheet with 3 tabs:
  Tab 1 "Research Library" — Steps 1-3: scan + transcript + analysis
  Tab 2 "Research Brief"   — Step 4: research agent output
  Tab 3 "Scripts"          — Step 5: writer agent output
"""

import os
import json
import gspread
from datetime import datetime
from config import GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_FILE


def _get_client():
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
    return gspread.authorize(creds)


def _get_or_create_sheet(gc, spreadsheet_id: str, tab_name: str, headers: list[str]):
    """Open spreadsheet, get or create a tab, write headers if new."""
    spreadsheet = gc.open_by_key(spreadsheet_id)
    try:
        ws = spreadsheet.worksheet(tab_name)
    except Exception:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))

    existing = ws.row_values(1)
    if existing != headers:
        ws.clear()
        ws.append_row(headers, value_input_option="USER_ENTERED")

    return ws


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ─── Tab 0: Topic Ideas ──────────────────────────────────────────────────────

TOPIC_HEADERS = [
    "Date Added", "Topic Title", "Full Prompt / Description",
    "Narrative Style", "Tone / Mood", "Key Hooks", "Status",
]


def export_topic_idea_to_sheets(
    title: str,
    description: str,
    narrative_style: str = "",
    tone: str = "",
    hooks: str = "",
    status: str = "Idea",
) -> None:
    """Write a topic idea to the 'Topic Ideas' tab."""
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        return

    gc = _get_client()
    ws = _get_or_create_sheet(gc, GOOGLE_SHEETS_ID, "Topic Ideas", TOPIC_HEADERS)

    ws.append_row(
        [_now(), title, description, narrative_style, tone, hooks, status],
        value_input_option="USER_ENTERED",
    )


# ─── Tab 1: Research Library (Steps 1–3) ─────────────────────────────────────

LIBRARY_HEADERS = [
    "Research Date", "Label", "Video Title", "Channel", "URL",
    "Views", "Publish Date", "Transcript Words",
    "Hook Style", "Intro Pattern", "Pacing",
    "Tone", "Narrative Voice", "Vocabulary Level",
    "Recurring Phrases", "Rhetorical Devices", "Emotional Triggers",
    "Primary Topic", "Subtopics", "Psychological Concepts",
    "Target Audience", "Knowledge Level",
    "Main Points", "Engagement Factors", "Content Gaps", "Suggested Tags",
]


def export_analysis_to_sheets(label: str, items: list[dict]) -> int:
    """
    Write analyzed videos to Tab 1 'Research Library'.
    Skips rows where the video URL already exists (no duplicates).
    Returns number of rows added.
    """
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        print("  Google Sheets not configured — skipping export.")
        return 0

    gc = _get_client()
    ws = _get_or_create_sheet(gc, GOOGLE_SHEETS_ID, "Research Library", LIBRARY_HEADERS)

    # Collect existing URLs to avoid duplicates
    existing_urls = set(ws.col_values(5)[1:])  # column 5 = URL, skip header

    rows_added = 0
    for item in items:
        meta = item.get("video_meta", {})
        analysis = item.get("analysis") or {}
        transcript = item.get("transcript_data") or {}

        url = meta.get("url", "")
        if url in existing_urls:
            continue

        cs = analysis.get("content_structure", {})
        ws_ = analysis.get("writing_style", {})
        ta = analysis.get("topic_analysis", {})

        row = [
            _now(),
            label,
            meta.get("title", ""),
            meta.get("channel", ""),
            url,
            meta.get("view_count", 0),
            meta.get("publish_date", "")[:10],
            transcript.get("word_count", ""),
            cs.get("hook_style", ""),
            cs.get("intro_pattern", ""),
            cs.get("pacing", ""),
            ws_.get("tone", ""),
            ws_.get("narrative_voice", ""),
            ws_.get("vocabulary_level", ""),
            ", ".join(ws_.get("recurring_phrases", [])),
            ", ".join(ws_.get("rhetorical_devices", [])),
            ", ".join(ws_.get("emotional_triggers", [])),
            ta.get("primary_topic", ""),
            ", ".join(ta.get("subtopics", [])),
            ", ".join(ta.get("psychological_concepts", [])),
            ta.get("target_audience", ""),
            ta.get("knowledge_level_required", ""),
            " | ".join(analysis.get("main_points", [])),
            " | ".join(analysis.get("engagement_factors", [])),
            " | ".join(analysis.get("content_gaps", [])),
            ", ".join(analysis.get("suggested_tags", [])),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        existing_urls.add(url)
        rows_added += 1

    return rows_added


# ─── Tab 2: Research Brief (Step 4) ──────────────────────────────────────────

BRIEF_HEADERS = [
    "Date", "Topic", "Angle", "Niche",
    "Hook Angles", "Key Concepts", "Narrative Arc",
    "Suggested Sections", "Supporting Material", "Content Gaps to Address",
]


def export_brief_to_sheets(brief: dict) -> None:
    """Write research brief to Tab 2 'Research Brief'."""
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        print("  Google Sheets not configured — skipping export.")
        return

    gc = _get_client()
    ws = _get_or_create_sheet(gc, GOOGLE_SHEETS_ID, "Research Brief", BRIEF_HEADERS)

    def _join(items, key=None):
        """Join a list of strings or dicts into a readable string."""
        if not items:
            return ""
        if isinstance(items[0], dict):
            return " | ".join(str(item.get(key, item)) for item in items) if key else " | ".join(str(i) for i in items)
        return " | ".join(str(i) for i in items)

    arc = brief.get("narrative_arc", {})
    arc_str = f"Problem: {arc.get('problem_setup','')} → Journey: {arc.get('journey','')} → Resolution: {arc.get('resolution','')}" if isinstance(arc, dict) else str(arc)

    row = [
        _now(),
        brief.get("topic", ""),
        brief.get("angle", brief.get("core_question", "")),
        brief.get("niche", ""),
        _join(brief.get("hook_angles", [])),
        _join(brief.get("key_concepts", []), key="concept"),
        arc_str,
        _join(brief.get("suggested_sections", []), key="title"),
        _join(brief.get("supporting_material", []), key="content"),
        _join(brief.get("content_gaps_to_address", [])),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")


# ─── Tab 3: Scripts (Step 5) ─────────────────────────────────────────────────

SCRIPT_HEADERS = [
    # Writer columns
    "Script #", "Date", "Title", "Topic", "Target Minutes", "Word Count Est.",
    "Scene #", "Scene Label", "Script Text", "Writer Image Prompt",
    # Director columns
    "Director Image Prompt", "Director Negative Prompt",
    "Color Palette", "Mood", "Pacing Note", "On-Screen Text",
    "Visual Throughline", "Color Story",
]

# Column index map (0-based) for targeted updates
_COL = {h: i for i, h in enumerate(SCRIPT_HEADERS)}


def _get_script_number(ws, title: str) -> int:
    """Return existing script number for title, or next available number."""
    all_rows = ws.get_all_values()[1:]
    existing_titles = {row[_COL["Title"]]: row[_COL["Script #"]]
                       for row in all_rows if len(row) > _COL["Title"]}
    if title in existing_titles:
        return existing_titles[title]
    return len({v for v in existing_titles.values()}) + 1


def export_script_to_sheets(script: dict) -> None:
    """Write Writer script scenes to 'Scripts' tab. One row per scene."""
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        print("  Google Sheets not configured — skipping export.")
        return

    gc = _get_client()
    ws = _get_or_create_sheet(gc, GOOGLE_SHEETS_ID, "Scripts", SCRIPT_HEADERS)

    title = script.get("title", "")
    script_number = _get_script_number(ws, title)
    date = _now()
    topic = script.get("topic", "")
    minutes = script.get("target_minutes", "")
    word_count = script.get("word_count_estimate", "")

    for scene in script.get("scenes", []):
        # Build full-width row (Director columns left blank)
        row = [""] * len(SCRIPT_HEADERS)
        row[_COL["Script #"]]          = script_number
        row[_COL["Date"]]              = date
        row[_COL["Title"]]             = title
        row[_COL["Topic"]]             = topic
        row[_COL["Target Minutes"]]    = minutes
        row[_COL["Word Count Est."]]   = word_count
        row[_COL["Scene #"]]           = scene.get("scene_number", "")
        row[_COL["Scene Label"]]       = scene.get("label", "")
        row[_COL["Script Text"]]       = scene.get("script", "")
        row[_COL["Writer Image Prompt"]] = scene.get("image_prompt", "")
        ws.append_row(row, value_input_option="USER_ENTERED")


def export_directed_script_to_sheets(directed: dict) -> None:
    """
    Update existing Script rows with Director fields.
    Matches rows by Script # + Scene # and fills Director columns in-place.
    """
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        print("  Google Sheets not configured — skipping export.")
        return

    gc = _get_client()
    ws = _get_or_create_sheet(gc, GOOGLE_SHEETS_ID, "Scripts", SCRIPT_HEADERS)

    title = directed.get("title", "")
    visual_throughline = directed.get("visual_throughline", "")
    color_story = directed.get("color_story", "")

    all_rows = ws.get_all_values()  # includes header at index 0
    script_number = _get_script_number(ws, title)

    # Build a lookup: scene_number → spreadsheet row index (1-based)
    scene_row_map = {}
    for i, row in enumerate(all_rows[1:], start=2):  # start=2 = row 2 in Sheets
        if len(row) > _COL["Script #"] and str(row[_COL["Script #"]]) == str(script_number):
            scene_num = row[_COL["Scene #"]]
            scene_row_map[str(scene_num)] = i

    # Build all cell updates in one batch to avoid rate limits
    batch = []
    for scene in directed.get("scenes", []):
        scene_num = str(scene.get("scene_number", ""))
        if scene_num not in scene_row_map:
            continue
        sheet_row = scene_row_map[scene_num]
        palette = ", ".join(scene.get("color_palette", []))

        updates = {
            "Director Image Prompt":    scene.get("image_prompt", ""),
            "Director Negative Prompt": scene.get("image_negative_prompt", ""),
            "Color Palette":            palette,
            "Mood":                     scene.get("mood", ""),
            "Pacing Note":              scene.get("pacing_note", ""),
            "On-Screen Text":           scene.get("onscreen_text") or "",
            "Visual Throughline":       visual_throughline,
            "Color Story":              color_story,
        }
        for col_name, value in updates.items():
            col_idx = _COL[col_name] + 1  # gspread is 1-based
            batch.append({
                "range": gspread.utils.rowcol_to_a1(sheet_row, col_idx),
                "values": [[value]],
            })

    if batch:
        ws.batch_update(batch, value_input_option="USER_ENTERED")


# ─── Pull Scripts from Sheets → JSON ─────────────────────────────────────────

def pull_scripts_from_sheets(script_numbers: list = None) -> list:
    """
    Read the Scripts tab and reconstruct directed script JSON(s).
    If script_numbers given, only pull those. Otherwise pull all.
    Returns list of reconstructed script dicts.
    """
    if not GOOGLE_SHEETS_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        raise RuntimeError("Google Sheets not configured.")

    gc = _get_client()
    ws = gc.open_by_key(GOOGLE_SHEETS_ID).worksheet("Scripts")
    all_rows = ws.get_all_values()
    if not all_rows:
        return []

    headers = all_rows[0]
    col = {h: i for i, h in enumerate(headers)}
    data_rows = all_rows[1:]

    def _get(row, name):
        i = col.get(name, -1)
        return row[i].strip() if i >= 0 and i < len(row) else ""

    # Group rows by Script #
    from collections import defaultdict, OrderedDict
    scripts_by_num = OrderedDict()
    for row in data_rows:
        num = _get(row, "Script #")
        if num:
            scripts_by_num.setdefault(num, []).append(row)

    results = []
    for num, rows in scripts_by_num.items():
        if script_numbers and int(num) not in script_numbers:
            continue

        first = rows[0]
        title              = _get(first, "Title")
        topic              = _get(first, "Topic")
        target_minutes     = _get(first, "Target Minutes")
        visual_throughline = _get(first, "Visual Throughline")
        color_story        = _get(first, "Color Story")

        scenes = []
        for row in rows:
            # Use Director Image Prompt if filled, else fall back to Writer
            director_prompt = _get(row, "Director Image Prompt")
            writer_prompt   = _get(row, "Writer Image Prompt")
            image_prompt    = director_prompt if director_prompt else writer_prompt

            palette_str = _get(row, "Color Palette")
            palette = [p.strip() for p in palette_str.split(",") if p.strip()] if palette_str else []
            onscreen  = _get(row, "On-Screen Text")
            scene_num = _get(row, "Scene #")

            scenes.append({
                "scene_number":          int(scene_num) if scene_num.isdigit() else scene_num,
                "label":                 _get(row, "Scene Label"),
                "script":                _get(row, "Script Text"),
                "image_prompt":          image_prompt,
                "writer_image_prompt":   writer_prompt,
                "director_image_prompt": director_prompt,
                "image_negative_prompt": _get(row, "Director Negative Prompt"),
                "color_palette":         palette,
                "mood":                  _get(row, "Mood"),
                "pacing_note":           _get(row, "Pacing Note"),
                "onscreen_text":         onscreen if onscreen else None,
            })

        results.append({
            "script_number":     int(num) if num.isdigit() else num,
            "title":             title,
            "topic":             topic,
            "target_minutes":    int(target_minutes) if str(target_minutes).isdigit() else target_minutes,
            "visual_throughline": visual_throughline,
            "color_story":       color_story,
            "scenes":            scenes,
        })

    return results
