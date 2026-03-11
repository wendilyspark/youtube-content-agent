"""
Storage helpers: save/load scan results and generated scripts as JSON.
Uses 'label' as the primary key (replaces the old fixed 'topic' concept).
Label can be anything: a preset name, a slugified query, a video ID, a channel name.
"""

import json
import os
import glob
from datetime import datetime
from config import OUTPUT_DIR, SCRIPTS_DIR, PROJECTS_DIR


def _ensure_dirs():
    for d in (OUTPUT_DIR, SCRIPTS_DIR, PROJECTS_DIR):
        os.makedirs(d, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ─── Scan results ─────────────────────────────────────────────────────────────

def save_scan(label: str, videos: list[dict]) -> str:
    """Save scanned video metadata to JSON. Returns file path."""
    _ensure_dirs()
    filename = os.path.join(OUTPUT_DIR, f"scan_{label}_{_timestamp()}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"label": label, "scanned_at": _timestamp(), "video_count": len(videos), "videos": videos},
                  f, indent=2, ensure_ascii=False)
    return filename


# ─── Analysis results ─────────────────────────────────────────────────────────

def save_analysis(label: str, items: list[dict]) -> str:
    """Save full analysis results (meta + transcript + analysis) to JSON."""
    _ensure_dirs()
    filename = os.path.join(OUTPUT_DIR, f"analysis_{label}_{_timestamp()}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"label": label, "analyzed_at": _timestamp(), "item_count": len(items), "items": items},
                  f, indent=2, ensure_ascii=False)
    return filename


def load_latest_analysis(label: str | None = None) -> list[dict]:
    """
    Load the most recent analysis file.
    If label is given, matches files starting with analysis_{label}_.
    Otherwise loads the single most recent analysis file of any label.
    """
    _ensure_dirs()
    pattern = os.path.join(OUTPUT_DIR, f"analysis_{label}_*.json" if label else "analysis_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return []
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", [])


def load_all_analyses(labels: list[str] | None = None) -> list[dict]:
    """
    Load and merge items from multiple analysis files.
    If labels given, loads latest file for each. Otherwise loads all latest files (one per unique label).
    """
    _ensure_dirs()
    if labels:
        items = []
        for label in labels:
            items.extend(load_latest_analysis(label))
        return items

    # Find latest file per unique label prefix
    all_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "analysis_*.json")), reverse=True)
    seen_labels = set()
    items = []
    for f in all_files:
        basename = os.path.basename(f)
        # Extract label: analysis_{label}_{timestamp}.json
        # Timestamp is always 15 chars (YYYYMMDD_HHMMSS)
        label_part = basename[len("analysis_"):-len("_YYYYMMDD_HHMMSS.json")]
        # More robustly: strip trailing _timestamp
        parts = basename[len("analysis_"):-len(".json")].rsplit("_", 2)
        label_key = "_".join(parts[:-2]) if len(parts) > 2 else parts[0]
        if label_key not in seen_labels:
            seen_labels.add(label_key)
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            items.extend(data.get("items", []))
    return items


def list_analysis_labels() -> list[str]:
    """Return all unique labels that have saved analysis files."""
    _ensure_dirs()
    files = glob.glob(os.path.join(OUTPUT_DIR, "analysis_*.json"))
    labels = set()
    for f in files:
        basename = os.path.basename(f)
        parts = basename[len("analysis_"):-len(".json")].rsplit("_", 2)
        label = "_".join(parts[:-2]) if len(parts) > 2 else parts[0]
        labels.add(label)
    return sorted(labels)


# ─── Overview ────────────────────────────────────────────────────────────────

def list_outputs() -> None:
    """Print a summary of all saved output files grouped by type."""
    _ensure_dirs()
    sections = [
        ("Scans", OUTPUT_DIR, "scan_"),
        ("Analyses", OUTPUT_DIR, "analysis_"),
        ("Scripts", SCRIPTS_DIR, "draft_"),
        ("Projects", PROJECTS_DIR, ""),
    ]
    for section_name, directory, prefix in sections:
        files = sorted(
            [f for f in os.listdir(directory) if f.startswith(prefix) and not os.path.isdir(os.path.join(directory, f))],
            reverse=True
        )
        print(f"\n{section_name} ({directory}):")
        if not files:
            print("  (empty)")
        for fname in files[:10]:
            size = os.path.getsize(os.path.join(directory, fname))
            print(f"  {fname}  ({size:,} bytes)")

    labels = list_analysis_labels()
    if labels:
        print(f"\nAvailable analysis labels: {', '.join(labels)}")
