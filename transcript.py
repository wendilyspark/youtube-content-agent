"""
Skill 2: Transcript Extractor
Fetches and structures transcripts from YouTube videos.
Uses cookies file when available to bypass YouTube IP blocks.
"""

import os
import requests as _requests
from config import PREFERRED_LANGUAGE, YOUTUBE_COOKIES_FILE, TRANSCRIPT_REQUEST_DELAY, WEBSHARE_PROXY_URL


def fetch_transcript(video_id: str) -> list[dict] | None:
    """
    Fetch transcript via yt-dlp (primary) with fallback to youtube-transcript-api.
    Returns list of {text, start, duration} dicts, or None if unavailable.
    """
    result = _fetch_via_ytdlp(video_id)
    if result is not None:
        return result
    return _fetch_via_api(video_id)


def _fetch_via_ytdlp(video_id: str) -> list[dict] | None:
    """
    Use yt-dlp subprocess to download subtitle files into a temp dir, then parse.
    This bypasses yt-dlp's format-validation crash when only subtitles are needed.
    """
    import subprocess
    import tempfile
    import json as _json

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "python3", "-m", "yt_dlp",
                "--skip-download",
                "--write-auto-subs",
                "--write-subs",
                "--sub-langs", f"{PREFERRED_LANGUAGE}-orig,{PREFERRED_LANGUAGE}",
                "--sub-format", "json3",
                "--output", os.path.join(tmpdir, "%(id)s"),
                "--quiet", "--no-warnings",
            ]
            if os.path.exists(YOUTUBE_COOKIES_FILE):
                cmd.extend(["--cookies", YOUTUBE_COOKIES_FILE])
            if WEBSHARE_PROXY_URL:
                cmd.extend(["--proxy", WEBSHARE_PROXY_URL])
            cmd.append(f"https://www.youtube.com/watch?v={video_id}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Find any .json3 subtitle file written
            sub_files = [f for f in os.listdir(tmpdir) if f.endswith(".json3")]
            if not sub_files:
                return None

            with open(os.path.join(tmpdir, sub_files[0]), encoding="utf-8") as f:
                data = _json.load(f)
            return _parse_json3(data)

    except Exception as e:
        print(f"  yt-dlp transcript error for {video_id}: {e}")
        return None


def _parse_json3(data: dict) -> list[dict]:
    """Parse YouTube json3 subtitle format into {text, start, duration} list."""
    segments = []
    for event in data.get("events", []):
        if "segs" not in event:
            continue
        start_ms = event.get("tStartMs", 0)
        duration_ms = event.get("dDurationMs", 0)
        text = "".join(seg.get("utf8", "") for seg in event["segs"]).strip()
        if text and text != "\n":
            segments.append({
                "text": text,
                "start": start_ms / 1000,
                "duration": duration_ms / 1000,
            })
    return segments or None


def _parse_vtt(vtt_text: str) -> list[dict]:
    """Parse WebVTT subtitle format into {text, start, duration} list."""
    import re
    segments = []
    blocks = vtt_text.strip().split("\n\n")
    time_pattern = re.compile(r"(\d+:\d+:\d+\.\d+|\d+:\d+\.\d+) --> (\d+:\d+:\d+\.\d+|\d+:\d+\.\d+)")
    for block in blocks:
        lines = block.strip().splitlines()
        match = None
        text_lines = []
        for line in lines:
            m = time_pattern.match(line)
            if m:
                match = m
            elif match and line and not line.startswith("WEBVTT"):
                # Strip HTML tags
                text_lines.append(re.sub(r"<[^>]+>", "", line).strip())
        if match and text_lines:
            start = _vtt_time_to_seconds(match.group(1))
            end = _vtt_time_to_seconds(match.group(2))
            text = " ".join(text_lines).strip()
            if text:
                segments.append({"text": text, "start": start, "duration": end - start})
    return segments or None


def _vtt_time_to_seconds(t: str) -> float:
    parts = t.replace(",", ".").split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return int(parts[0]) * 60 + float(parts[1])


def _fetch_via_api(video_id: str) -> list[dict] | None:
    """Fallback: youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
        kwargs = {}
        if WEBSHARE_PROXY_URL:
            kwargs["proxies"] = {"https": WEBSHARE_PROXY_URL, "http": WEBSHARE_PROXY_URL}
        api = YouTubeTranscriptApi(**kwargs)
        transcript_list = api.list(video_id)
        try:
            t = transcript_list.find_manually_created_transcript([PREFERRED_LANGUAGE])
        except Exception:
            try:
                t = transcript_list.find_generated_transcript([PREFERRED_LANGUAGE])
            except Exception:
                t = transcript_list.find_transcript([PREFERRED_LANGUAGE])
        fetched = t.fetch()
        return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
    except Exception:
        return None


def format_transcript_text(raw: list[dict]) -> str:
    """Convert raw transcript segments to plain text."""
    return " ".join(seg["text"] for seg in raw).strip()


def segment_transcript(raw: list[dict], segment_gap_seconds: float = 30.0) -> list[dict]:
    """
    Group transcript segments into logical sections based on time gaps.
    Returns list of {start, end, text} section dicts.
    """
    if not raw:
        return []

    sections = []
    current_texts = []
    current_start = raw[0]["start"]
    prev_end = raw[0]["start"] + raw[0].get("duration", 0)

    for seg in raw:
        gap = seg["start"] - prev_end
        if gap > segment_gap_seconds and current_texts:
            sections.append({
                "start_seconds": current_start,
                "end_seconds": prev_end,
                "start_formatted": format_seconds(current_start),
                "text": " ".join(current_texts),
            })
            current_texts = []
            current_start = seg["start"]

        current_texts.append(seg["text"])
        prev_end = seg["start"] + seg.get("duration", 0)

    if current_texts:
        sections.append({
            "start_seconds": current_start,
            "end_seconds": prev_end,
            "start_formatted": format_seconds(current_start),
            "text": " ".join(current_texts),
        })

    return sections


def format_seconds(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def get_structured_transcript(video_id: str) -> dict | None:
    """
    Full pipeline: fetch → structure → return dict with full text and sections.
    Returns None if transcript unavailable.
    """
    raw = fetch_transcript(video_id)
    if raw is None:
        return None

    full_text = format_transcript_text(raw)
    sections = segment_transcript(raw)
    duration = raw[-1]["start"] + raw[-1].get("duration", 0) if raw else 0

    return {
        "video_id": video_id,
        "duration_seconds": duration,
        "duration_formatted": format_seconds(duration),
        "segment_count": len(sections),
        "word_count": len(full_text.split()),
        "full_text": full_text,
        "sections": sections,
    }
