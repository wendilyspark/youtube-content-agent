#!/usr/bin/env python3
"""
YouTube Agent — Main Orchestrator
Each step is a separate command you control. Nothing auto-advances.

COMMANDS:
  scan         — Scout Agent: find/benchmark videos (flexible input)
  analyze      — Re-run Claude analysis on saved transcript data (no YouTube calls)
  research     — Research Agent: deep-dive your topic, produce content brief
  write        — Writer Agent: generate script draft from brief + style library
  direct       — Director Agent: enrich approved script with visuals & pacing
  voices       — Preview ElevenLabs voices with audio demos
  produce      — Media Agent: generate images + voiceover + captions → MP4
  regen-audio  — Regenerate voiceover for specific scenes after Sheets script edits
  preview      — Render scenes to MP4 with Ken Burns + captions (Pillow + ffmpeg)
  pull-script  — Pull edited scripts from Google Sheets → rebuild local JSON
  list         — List all saved output files and available labels

SCAN EXAMPLES:
  # Topic label from topics.json (prompts you to define it if new)
  python main.py scan --topics fitness stoicism

  # Free-form search query
  python main.py scan --query "stoic philosophy daily habits" --label stoicism_habits

  # Specific video URLs to benchmark
  python main.py scan --video https://youtu.be/ABC123 https://youtu.be/XYZ456

  # Entire channel
  python main.py scan --channel https://www.youtube.com/@AcademyOfIdeas

  # Mix: channel + extra label name
  python main.py scan --channel https://www.youtube.com/@Einzelganger --label einzelganger

TYPICAL FLOW:
  1. python main.py scan --topics <your_topic>    # define new topics interactively
  2. python main.py analyze --label <your_topic>
  3. python main.py research --topic "your video topic"
  4. python main.py write --label <your_topic> --minutes 10
         ⏸ review output/scripts/draft_*.json, edit as needed
  5. python main.py direct
  6. python main.py voices
  7. python main.py produce --voice daniel
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from config import YOUTUBE_API_KEY, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, STABILITY_API_KEY
from config import OUTPUT_DIR, SCRIPTS_DIR, PROJECTS_DIR
from config import GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_FILE


def _ensure_dirs():
    for d in (OUTPUT_DIR, SCRIPTS_DIR, PROJECTS_DIR):
        os.makedirs(d, exist_ok=True)


def check_keys(*required):
    key_map = {
        "youtube":    ("YOUTUBE_API_KEY",    YOUTUBE_API_KEY),
        "anthropic":  ("ANTHROPIC_API_KEY",  ANTHROPIC_API_KEY),
        "elevenlabs": ("ELEVENLABS_API_KEY", ELEVENLABS_API_KEY),
        "stability":  ("STABILITY_API_KEY",  STABILITY_API_KEY),
    }
    missing = [env for name in required for env, val in [key_map[name]] if not val]
    if missing:
        print("ERROR: Missing API keys. Add them to .env or set as environment variables:")
        for k in missing:
            print(f"  {k}=your_key_here")
        sys.exit(1)


def save_json(data: dict, prefix: str) -> str:
    from datetime import datetime
    _ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPTS_DIR, f"{prefix}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def latest_file(prefix: str) -> str | None:
    """Find most recent file in SCRIPTS_DIR matching prefix."""
    _ensure_dirs()
    matches = sorted([
        f for f in os.listdir(SCRIPTS_DIR)
        if f.startswith(prefix) and f.endswith(".json")
    ], reverse=True)
    return os.path.join(SCRIPTS_DIR, matches[0]) if matches else None


def _fetch_transcripts_and_save(label: str, videos: list[dict]) -> list[dict]:
    """Shared helper: fetch transcripts for a list of videos, return items list."""
    import time, random
    from transcript import get_structured_transcript
    from storage import save_scan
    from config import TRANSCRIPT_REQUEST_DELAY

    scan_path = save_scan(label, videos)
    print(f"Saved scan → {scan_path}")
    print(f"\nFetching transcripts for '{label}' ({len(videos)} videos)...")

    items = []
    for i, v in enumerate(videos):
        print(f"  [{i+1}/{len(videos)}] {v['title'][:65]}...")
        t = get_structured_transcript(v["video_id"])
        if t:
            items.append({"video_meta": v, "transcript_data": t})
        else:
            print("    No transcript — skipped.")
        if i < len(videos) - 1:
            delay = TRANSCRIPT_REQUEST_DELAY + random.uniform(0, 1.0)
            time.sleep(delay)
    return items


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_scan(args):
    check_keys("youtube")
    from storage import save_analysis

    # Determine scan mode — mutually exclusive inputs
    has_topics   = bool(args.topics)
    has_query    = bool(args.query)
    has_videos   = bool(args.video)
    has_channel  = bool(args.channel)

    # --query is allowed alongside --channel (acts as topic filter within channel)
    standalone_modes = [has_topics, has_query and not has_channel, has_videos, has_channel]
    if sum(standalone_modes) == 0 and not has_channel:
        print("ERROR: Provide one of --topics, --query, --video, or --channel.")
        print("Run 'python main.py scan --help' for examples.")
        sys.exit(1)
    if has_topics and (has_query or has_videos or has_channel):
        print("ERROR: --topics cannot be combined with other source flags.")
        sys.exit(1)
    if has_videos and (has_query or has_channel):
        print("ERROR: --video cannot be combined with other source flags.")
        sys.exit(1)

    all_items = []  # list of (label, items_with_transcripts)

    if has_topics:
        from scanner import scan_topic
        for topic in args.topics:
            print(f"\nScanning topic: '{topic}'")
            label, videos = scan_topic(topic, queries=args.queries or None)
            print(f"  Found {len(videos)} videos")
            items = _fetch_transcripts_and_save(label, videos)
            all_items.append((label, items))

    elif has_channel:
        # Channel must be checked before standalone query — query is an optional topic filter here
        from scanner import scan_channel
        label = args.label or None
        topic_filter = args.query or ""
        print(f"\nScanning channel: {args.channel}")
        label, videos = scan_channel(args.channel, label=label, max_results=args.max_results, query=topic_filter)
        print(f"  Found {len(videos)} videos (label: '{label}')")
        items = _fetch_transcripts_and_save(label, videos)
        all_items.append((label, items))

    elif has_query:
        from scanner import scan_query
        label = args.label or None
        print(f"\nSearching: '{args.query}'")
        label, videos = scan_query(args.query, label=label)
        print(f"  Found {len(videos)} videos (label: '{label}')")
        items = _fetch_transcripts_and_save(label, videos)
        all_items.append((label, items))

    elif has_videos:
        from scanner import scan_video_urls
        label = args.label or None
        print(f"\nFetching {len(args.video)} specific video(s)...")
        label, videos = scan_video_urls(args.video, label=label)
        print(f"  Fetched {len(videos)} videos (label: '{label}')")
        items = _fetch_transcripts_and_save(label, videos)
        all_items.append((label, items))

    # Save transcript data (without Claude analysis — run 'analyze' separately)
    for label, items in all_items:
        if items:
            # Save as analysis file with null analyses so 'analyze' can pick it up
            placeholder = [{"video_meta": it["video_meta"], "transcript_data": it["transcript_data"], "analysis": None}
                           for it in items]
            apath = save_analysis(label, placeholder)
            print(f"\nTranscripts saved → {apath}")
            print(f"  {len(items)} videos ready for analysis.")
            print(f"\nNext: python main.py analyze --label {label}")
        else:
            print(f"\nNo transcripts retrieved for '{label}'.")

    print("\nScan complete.")


def cmd_fetch_transcripts(args):
    """Retry transcript fetching for already-scanned videos (uses cookies if available)."""
    check_keys("youtube")
    import glob
    from storage import save_analysis

    labels = args.label if args.label else []
    if not labels:
        # Auto-detect from saved scan files
        scan_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "scan_*.json")), reverse=True)
        seen = set()
        for f in scan_files:
            # Extract label from filename: scan_{label}_{timestamp}.json
            basename = os.path.basename(f)[len("scan_"):-len(".json")]
            parts = basename.rsplit("_", 2)
            label = "_".join(parts[:-2]) if len(parts) > 2 else parts[0]
            if label not in seen:
                seen.add(label)
                labels.append(label)
        if not labels:
            print("No saved scan files found. Run 'scan' first.")
            sys.exit(1)
        print(f"Auto-detected labels: {', '.join(labels)}")

    for label in labels:
        # Match by exact label field in JSON, not just filename prefix
        all_scan_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "scan_*.json")), reverse=True)
        matched = None
        for sf in all_scan_files:
            try:
                with open(sf, encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("label") == label and d.get("videos"):
                    matched = (sf, d)
                    break
            except Exception:
                continue

        if not matched:
            print(f"\nNo scan file with label '{label}' and videos found. Run 'scan' first.")
            continue

        scan_file, saved = matched
        print(f"\nLoading scan: {os.path.basename(scan_file)}")
        videos = saved.get("videos", [])
        if not videos:
            print(f"\nNo videos in scan for '{label}'.")
            continue

        print(f"\nRetrying transcripts for '{label}' ({len(videos)} videos)...")
        items = _fetch_transcripts_and_save(label, videos)

        if items:
            placeholder = [{"video_meta": it["video_meta"], "transcript_data": it["transcript_data"], "analysis": None}
                           for it in items]
            apath = save_analysis(label, placeholder)
            print(f"  {len(items)}/{len(videos)} transcripts saved → {apath}")
            print(f"  Next: python main.py analyze --label {label}")
        else:
            print(f"  Still no transcripts for '{label}'. Check cookies.txt.")


def cmd_analyze(args):
    """Re-run Claude analysis on already-saved transcript data. No YouTube calls."""
    check_keys("anthropic")
    from analyzer import analyze_batch
    from storage import save_analysis, list_analysis_labels
    import glob

    # Determine which labels to analyze
    if args.label:
        labels = [args.label]
    else:
        labels = list_analysis_labels()
        if not labels:
            print("No saved analysis data found. Run 'scan' first.")
            sys.exit(1)
        print(f"Found labels: {', '.join(labels)}")

    for label in labels:
        pattern = os.path.join(OUTPUT_DIR, f"analysis_{label}_*.json")
        files = sorted(glob.glob(pattern), reverse=True)
        if not files:
            print(f"\nNo saved data for label '{label}' — run 'scan' first.")
            continue

        path = files[0]
        print(f"\nLoading: {os.path.basename(path)}")
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)

        items = saved.get("items", [])
        to_analyze = [it for it in items if not it.get("analysis")]
        already_done = len(items) - len(to_analyze)

        if not to_analyze:
            print(f"  All {len(items)} videos already analyzed — exporting to Sheets.")
            try:
                from sheets import export_analysis_to_sheets
                added = export_analysis_to_sheets(label, items)
                print(f"  Sheets: {added} new rows added to 'Research Library' tab." if added else "  Sheets: all rows already present.")
            except Exception as e:
                print(f"  Sheets export skipped: {e}")
            continue

        if already_done:
            print(f"  {already_done} already done, analyzing {len(to_analyze)} remaining...")
        else:
            print(f"  Analyzing {len(to_analyze)} videos...")

        fresh = analyze_batch(to_analyze)

        fresh_by_id = {it["video_meta"]["video_id"]: it for it in fresh}
        merged = [fresh_by_id.get(it["video_meta"]["video_id"], it) for it in items]

        apath = save_analysis(label, merged)
        success = sum(1 for it in merged if it.get("analysis"))
        print(f"  Done: {success}/{len(merged)} analyzed → {apath}")

        # Export to Google Sheets Tab 1
        try:
            from sheets import export_analysis_to_sheets
            added = export_analysis_to_sheets(label, merged)
            if added:
                print(f"  Sheets: {added} rows added to 'Research Library' tab.")
        except Exception as e:
            print(f"  Sheets export skipped: {e}")


def cmd_research(args):
    check_keys("anthropic")
    from research import research_topic, print_brief_summary

    print(f"Researching: '{args.topic}'")
    if args.angle:
        print(f"Your angle: '{args.angle}'")

    brief = research_topic(
        topic=args.topic,
        angle=args.angle or "",
        niche=args.niche or "",
    )
    print_brief_summary(brief)
    path = save_json(brief, "brief")
    print(f"Research brief saved → {path}")

    # Export to Google Sheets Tab 2 (brief) + Topic Ideas
    try:
        from sheets import export_brief_to_sheets, export_topic_idea_to_sheets
        export_brief_to_sheets(brief)
        print("  Sheets: research brief added to 'Research Brief' tab.")
        export_topic_idea_to_sheets(
            title=args.topic,
            description=args.angle or "",
            narrative_style=getattr(args, "voice_style", None) or "second-person (you)",
            tone=getattr(args, "tone", None) or "calm, intelligent, slightly philosophical",
            status="Researched",
        )
        print("  Sheets: topic saved to 'Topic Ideas' tab.")
    except Exception as e:
        print(f"  Sheets export skipped: {e}")

    print("\nNext: python main.py write")


def cmd_write(args):
    check_keys("anthropic")
    from writer import write_script, print_script_preview
    from storage import load_latest_analysis, load_all_analyses, list_analysis_labels

    # Load research brief
    brief_path = args.brief or latest_file("brief")
    if not brief_path or not os.path.exists(brief_path):
        print("No research brief found. Run 'research' first.")
        sys.exit(1)
    brief = load_json(brief_path)
    print(f"Using brief: {os.path.basename(brief_path)}")

    # Load style analyses — by label(s) or all available
    if args.label:
        labels = args.label  # list
        analyses = load_all_analyses(labels)
        print(f"Style sources: {', '.join(labels)}")
    else:
        analyses = load_all_analyses()
        available = list_analysis_labels()
        print(f"Style sources: all available ({', '.join(available) or 'none'})")

    if not analyses:
        print("Warning: no style analysis found. Run 'scan' + 'analyze' first for style references.")
        print("Continuing with default tone...\n")

    script = write_script(
        research_brief=brief,
        style_analyses=analyses,
        target_minutes=args.minutes,
        narrative_voice=args.voice_style or "second-person (you)",
        tone=args.tone or "calm, intelligent, slightly philosophical",
    )
    print_script_preview(script)
    path = save_json(script, "draft")
    print(f"\nScript draft saved → {path}")

    # Export to Google Sheets Tab 3 and auto-open for review
    try:
        from sheets import export_script_to_sheets
        export_script_to_sheets(script)
        print("  Sheets: script scenes added to 'Scripts' tab.")
        sheet_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/edit"
        import subprocess
        subprocess.run(["open", sheet_url], check=False)
        print(f"  Google Sheet opened in browser for review.")
    except Exception as e:
        print(f"  Sheets export skipped: {e}")
    print("\n⏸  Review and edit the script in Google Sheets (Scripts tab).")
    print("When ready: python main.py direct --script {path}")


def cmd_direct(args):
    check_keys("anthropic")
    from director import direct_script, print_shot_list

    script_path = args.script or latest_file("draft")
    if not script_path or not os.path.exists(script_path):
        print("No script found. Run 'write' first or pass --script <path>")
        sys.exit(1)

    script = load_json(script_path)
    print(f"Directing: '{script.get('title','')}'")

    directed = direct_script(script)
    print_shot_list(directed)
    path = save_json(directed, "directed")
    print(f"Directed script saved → {path}")

    # Export Director columns to Scripts tab in Google Sheets
    try:
        from sheets import export_directed_script_to_sheets
        export_directed_script_to_sheets(directed)
        print("  Sheets: Director columns updated in 'Scripts' tab.")
    except Exception as e:
        print(f"  Sheets export skipped: {e}")

    print("\n⏸  Review shot list above. When ready:")
    print("  python main.py voices")
    print(f"  python main.py produce --script {path}")


def cmd_voices(_args):
    check_keys("elevenlabs")
    from voices import interactive_voice_picker
    voice_id = interactive_voice_picker()
    print(f"\nChosen voice ID: {voice_id}")
    print(f"Use it with: python main.py produce --voice-id {voice_id}")


def cmd_produce(args):
    check_keys("elevenlabs", "stability")
    from media import produce_video
    from voices import CURATED_VOICES
    from config import DEFAULT_VOICE_ID

    # When resuming a project dir without an explicit --script, prefer the
    # directed_script.json saved inside that folder (avoids loading the wrong
    # most-recent global script).
    if not args.script and args.project_dir:
        proj_script = os.path.join(args.project_dir, "directed_script.json")
        if os.path.exists(proj_script):
            args.script = proj_script

    script_path = args.script or latest_file("directed")
    if not script_path or not os.path.exists(script_path):
        print("No directed script found. Run 'direct' first or pass --script <path>")
        sys.exit(1)

    directed = load_json(script_path)

    if args.voice_id:
        voice_id = args.voice_id
    elif args.voice:
        voice_id = CURATED_VOICES.get(args.voice.lower(), {}).get("id", DEFAULT_VOICE_ID)
    else:
        print("No voice specified. Launching voice picker...")
        from voices import interactive_voice_picker
        voice_id = interactive_voice_picker()

    print(f"\nProducing: '{directed.get('title','')}'")
    print(f"Voice: {voice_id}")
    final_path = produce_video(
        directed,
        voice_id=voice_id,
        project_dir=args.project_dir or None,
        style_preset=args.style or None,
        color_theme=args.color_theme or None,
    )
    print(f"\nFinal video: {final_path}")


def cmd_regen_audio(args):
    """Regenerate voiceover for specific scenes after Google Sheets script edits."""
    check_keys("elevenlabs")
    from media import generate_voiceover_with_timestamps
    from config import DEFAULT_VOICE_ID
    from voices import CURATED_VOICES

    if not args.script or not os.path.exists(args.script):
        print("--script is required. Use a JSON from pull-script first.")
        sys.exit(1)
    if not args.project_dir or not os.path.isdir(args.project_dir):
        print("--project-dir is required and must point to an existing project folder.")
        sys.exit(1)

    directed = load_json(args.script)
    scenes   = directed.get("scenes", [])

    if args.voice_id:
        voice_id = args.voice_id
    elif args.voice:
        voice_id = CURATED_VOICES.get(args.voice.lower(), {}).get("id", DEFAULT_VOICE_ID)
    else:
        voice_id = DEFAULT_VOICE_ID

    scene_nums = set(args.scenes) if args.scenes else {s["scene_number"] for s in scenes}
    audio_dir  = os.path.join(args.project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    for scene in scenes:
        n = scene["scene_number"]
        if n not in scene_nums:
            continue
        text     = scene.get("voiceover", scene.get("script", "")).replace("[PAUSE]", "...")
        out_path = os.path.join(audio_dir, f"scene_{n:02d}.mp3")
        ts_path  = os.path.join(audio_dir, f"scene_{n:02d}_timestamps.json")
        print(f"  Regenerating scene {n}...")
        try:
            audio_path, timestamps = generate_voiceover_with_timestamps(text, voice_id, out_path)
            with open(ts_path, "w") as f:
                json.dump(timestamps, f)
            print(f"    Saved: {audio_path}")
        except Exception as e:
            print(f"    Failed: {e}")

    print("\nDone. Run 'python main.py preview' to render the updated scenes.")


def cmd_preview(args):
    """Render specific scenes to a preview MP4 using Pillow + ffmpeg (Ken Burns + captions)."""
    from media import render_scenes_to_video

    if not args.project_dir or not os.path.isdir(args.project_dir):
        print("--project-dir is required and must point to an existing project folder.")
        sys.exit(1)

    scene_nums = args.scenes
    if not scene_nums:
        # Auto-detect from audio directory
        audio_dir = os.path.join(args.project_dir, "audio")
        mp3s      = sorted(glob.glob(os.path.join(audio_dir, "scene_*.mp3")))
        scene_nums = []
        for mp3 in mp3s:
            m = re.match(r"scene_(\d+)\.mp3", os.path.basename(mp3))
            if m:
                scene_nums.append(int(m.group(1)))

    if not scene_nums:
        print("No scenes found. Pass --scenes 1 2 3 or ensure audio/scene_XX.mp3 files exist.")
        sys.exit(1)

    shadow_color = (0, 0, 0)
    if args.shadow_color:
        parts = [int(x.strip()) for x in args.shadow_color.split(",")]
        if len(parts) == 3:
            shadow_color = tuple(parts)

    label    = "_".join(str(n) for n in scene_nums)
    out_path = os.path.join(args.project_dir, f"preview_{label}.mp4")
    print(f"\nRendering scenes: {scene_nums}")
    print(f"Output: {out_path}\n")

    render_scenes_to_video(scene_nums, args.project_dir, out_path,
                           caption_shadow_color=shadow_color)
    print(f"\nPreview ready: {out_path}")
    subprocess.run(["open", out_path], check=False)


def cmd_pull_script(args):
    """Pull edited scripts from Google Sheets → rebuild local JSON files."""
    from sheets import pull_scripts_from_sheets

    nums = args.number or None
    print(f"\nPulling {'script(s) ' + str(nums) if nums else 'all scripts'} from Google Sheets...")

    scripts = pull_scripts_from_sheets(script_numbers=nums)
    if not scripts:
        print("No scripts found in Sheets.")
        return

    for script in scripts:
        num   = script.get("script_number", "?")
        title = script.get("title", "untitled")
        path  = save_json(script, f"pulled_script{num}")
        print(f"\nScript #{num}: {title}")
        print(f"  {len(script.get('scenes', []))} scenes pulled from Sheets")
        print(f"  Saved → {path}")
        print(f"  Ready for: python main.py produce --script {path}")

    print("\nNote: 'image_prompt' per scene uses Director prompt if filled, else Writer prompt.")


def cmd_list(_args):
    from storage import list_outputs
    list_outputs()


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _startup_check():
    """Run on `python main.py` with no arguments: verify APIs, then show what to do next."""
    import glob
    from verify_apis import check_youtube, check_anthropic, check_elevenlabs, check_stability, check_sheets

    print("\n" + "="*50)
    print("  YouTube Agent — Ready Check")
    print("="*50 + "\n")

    results = {
        "YouTube":       check_youtube(),
        "Anthropic":     check_anthropic(),
        "ElevenLabs":    check_elevenlabs(),
        "Stability AI":  check_stability(),
        "Google Sheets": check_sheets(),
    }

    passed = sum(results.values())
    total  = len(results)
    print()

    if passed < total:
        failed = [k for k, v in results.items() if not v]
        print(f"  ✗  Fix these before continuing: {', '.join(failed)}")
        print("     Add missing keys to .env and re-run.\n")
        return

    print("  All APIs connected.\n")

    # Detect pipeline stage
    _ensure_dirs()
    has_analyses  = bool(glob.glob(os.path.join(OUTPUT_DIR, "analysis_*.json")))
    has_brief     = bool(glob.glob(os.path.join(SCRIPTS_DIR, "brief_*.json")))
    has_draft     = bool(glob.glob(os.path.join(SCRIPTS_DIR, "draft_*.json")))
    has_directed  = bool(glob.glob(os.path.join(SCRIPTS_DIR, "directed_*.json")))

    print("  What would you like to do?\n")
    if not has_analyses:
        print("  → First time? Build your style library:")
        print("    python main.py scan --topics <your_topic>")
        print("    python main.py analyze")
    elif not has_brief:
        print("  → Style library ready. Create your first video:")
        print('    python main.py research --topic "your topic" --angle "your angle"')
    elif not has_draft:
        print("  → Research brief ready. Write the script:")
        print("    python main.py write --minutes 10")
    elif not has_directed:
        print("  → Script draft ready. Review it in Google Sheets, then:")
        print("    python main.py direct")
    else:
        print("  → Directed script ready. Produce the video:")
        print("    python main.py voices")
        print("    python main.py produce --voice-id <ID>")

    print()
    print("  Run 'python main.py --help' to see all commands.\n")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Content Research & Video Production Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # ── scan ──────────────────────────────────────────────────────────────────
    p = sub.add_parser("scan", help="Scout: scan/benchmark YouTube videos (flexible input)")
    src = p.add_argument_group("source (pick one)")
    src.add_argument("--topics", nargs="+", metavar="TOPIC",
                     help="Topic label(s) from topics.json")
    p.add_argument("--queries", nargs="+", metavar="QUERY",
                   help="Search queries for a new topic label (skips interactive prompt)")
    src.add_argument("--query", metavar="TEXT",
                     help='Free-form search, e.g. "depth psychology anima animus"')
    src.add_argument("--video", nargs="+", metavar="URL",
                     help="One or more YouTube video URLs to benchmark directly")
    src.add_argument("--channel", metavar="URL_OR_HANDLE",
                     help="YouTube channel URL, @handle, or channel ID")
    p.add_argument("--label", metavar="NAME",
                   help="Custom label for saved files (auto-generated if omitted)")
    p.add_argument("--max-results", type=int, default=15, metavar="N",
                   help="Max videos to fetch from a channel (default: 15)")

    # ── fetch-transcripts ─────────────────────────────────────────────────────
    p = sub.add_parser("fetch-transcripts", help="Retry transcript fetching on saved scan data (add cookies.txt first)")
    p.add_argument("--label", nargs="+", metavar="LABEL",
                   help="Labels to retry (default: all saved scans)")

    # ── analyze ───────────────────────────────────────────────────────────────
    p = sub.add_parser("analyze", help="Claude analysis on saved transcript data (no YouTube calls)")
    p.add_argument("--label", metavar="LABEL",
                   help="Analyze a specific label (default: all saved labels)")

    # ── research ──────────────────────────────────────────────────────────────
    p = sub.add_parser("research", help="Research Agent: deep-dive your topic")
    p.add_argument("--topic", required=True, help='e.g. "shadow self in relationships"')
    p.add_argument("--angle", help="Your personal angle or thesis")
    p.add_argument("--niche", help="Content niche context for the research (e.g. 'fitness', 'personal finance')")

    # ── write ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("write", help="Writer Agent: generate script draft")
    p.add_argument("--brief", help="Path to research brief JSON (default: latest)")
    p.add_argument("--label", nargs="+", metavar="LABEL",
                   help="Borrow style from these labels (default: all available)")
    p.add_argument("--minutes", type=int, default=10, help="Target video length in minutes")
    p.add_argument("--voice-style", help="Narrative voice (default: second-person)")
    p.add_argument("--tone", help="Tone override (default: calm, intelligent, philosophical)")

    # ── direct ────────────────────────────────────────────────────────────────
    p = sub.add_parser("direct", help="Director Agent: add visuals & pacing to approved script")
    p.add_argument("--script", help="Path to draft JSON (default: latest draft)")

    # ── voices ────────────────────────────────────────────────────────────────
    sub.add_parser("voices", help="Preview ElevenLabs voices with audio demos")

    # ── produce ───────────────────────────────────────────────────────────────
    p = sub.add_parser("produce", help="Media Agent: images + voiceover + captions → MP4")
    p.add_argument("--script", help="Path to directed script JSON (default: latest directed)")
    p.add_argument("--voice", choices=["daniel", "adam", "rachel", "dorothy", "arnold", "george"],
                   help="Voice name from curated list (default: daniel)")
    p.add_argument("--voice-id", help="Raw ElevenLabs voice ID (overrides --voice)")
    p.add_argument("--project-dir", metavar="PATH",
                   help="Resume from an existing project folder (reuses saved images/audio)")
    p.add_argument("--style", metavar="PRESET",
                   choices=["cinematic","photographic","analog-film","digital-art",
                            "fantasy-art","neon-punk","comic-book","enhance"],
                   help="Image style preset (open style_picker.html to preview options)")
    p.add_argument("--color-theme", metavar="THEME",
                   choices=["dark_mysterious","warm_golden","ethereal","earth_forest",
                            "cosmic","sunset","monochrome"],
                   help="Color theme applied to all image prompts (open style_picker.html to preview)")

    # ── pull-script ───────────────────────────────────────────────────────────
    p = sub.add_parser("pull-script", help="Pull edited scripts from Google Sheets → rebuild local JSON")
    p.add_argument("--number", nargs="+", type=int, metavar="N",
                   help="Script number(s) to pull (default: all). e.g. --number 1 2")

    # ── regen-audio ───────────────────────────────────────────────────────────
    p = sub.add_parser("regen-audio",
                       help="Regenerate voiceover for specific scenes after Sheets edits")
    p.add_argument("--script", required=True,
                   help="Path to pulled/directed script JSON (from pull-script)")
    p.add_argument("--project-dir", required=True, metavar="PATH",
                   help="Existing project folder (audio/ subdir will be updated)")
    p.add_argument("--scenes", nargs="+", type=int, metavar="N",
                   help="Scene numbers to regenerate (default: all)")
    p.add_argument("--voice", choices=["daniel", "adam", "rachel", "dorothy", "arnold", "george"],
                   help="Voice name (default: daniel)")
    p.add_argument("--voice-id", help="Raw ElevenLabs voice ID (overrides --voice)")

    # ── preview ───────────────────────────────────────────────────────────────
    p = sub.add_parser("preview",
                       help="Render scenes to MP4 with Ken Burns + captions (Pillow + ffmpeg)")
    p.add_argument("--project-dir", required=True, metavar="PATH",
                   help="Project folder containing images/ and audio/ subdirs")
    p.add_argument("--scenes", nargs="+", type=int, metavar="N",
                   help="Scene numbers to render (default: all available)")
    p.add_argument("--shadow-color", metavar="R,G,B",
                   help='Caption outline color e.g. "20,45,55" (default: 0,0,0 black)')

    # ── list ──────────────────────────────────────────────────────────────────
    sub.add_parser("list", help="List all saved files and available labels")

    args = parser.parse_args()
    commands = {
        "scan":               cmd_scan,
        "fetch-transcripts":  cmd_fetch_transcripts,
        "analyze":            cmd_analyze,
        "research": cmd_research,
        "write":    cmd_write,
        "direct":   cmd_direct,
        "voices":   cmd_voices,
        "produce":      cmd_produce,
        "regen-audio":  cmd_regen_audio,
        "preview":      cmd_preview,
        "pull-script":  cmd_pull_script,
        "list":         cmd_list,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        _startup_check()


if __name__ == "__main__":
    main()
