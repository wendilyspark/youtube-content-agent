"""
Agent 3: Writer Agent
Combines research brief + YouTube style library to write an original script.
Outputs a draft for human review — nothing proceeds until approved.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

WRITER_PROMPT = """You are a masterful YouTube scriptwriter for the psychology and consciousness niche.

Your job: write a fully original video script using the research brief below.
You must BORROW the writing STYLE from the reference sources — their tone, pacing, hook technique, vocabulary level, and emotional triggers.
You must NOT borrow their content. All ideas come from the research brief only.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH BRIEF:
{research_json}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STYLE REFERENCES (borrow these patterns only):
{style_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRIPT REQUIREMENTS:
- Target length: {target_minutes} minutes (~{word_count} words at 130wpm)
- Narrative voice: {narrative_voice}
- Tone: {tone}
- Open with ONE of the hook angles from the brief — make it visceral and immediate
- Follow the suggested sections from the brief as a structural guide
- Add [PAUSE] for 1-2 second dramatic beats
- Add [IMAGE: vivid description] at each scene change — these will become AI-generated visuals
- Captions will be auto-synced to audio, so write naturally spoken sentences
- End with a genuine, non-pushy call to reflect or engage

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — return ONLY valid JSON:
{{
  "title": "Final suggested title",
  "hook_used": "which hook angle you chose and why",
  "target_minutes": {target_minutes},
  "estimated_word_count": 0,
  "scenes": [
    {{
      "scene_number": 1,
      "label": "HOOK",
      "timestamp_estimate": "0:00",
      "image_prompt": "Detailed visual description for AI image generation (style: cinematic, psychological, symbolic)",
      "script": "The actual words spoken in this scene. Write naturally for speaking, not reading."
    }}
  ],
  "suggested_tags": ["tag1", "tag2"],
  "thumbnail_concept": "One-line thumbnail visual idea"
}}"""


def build_style_summary(analyses: list[dict], max_sources: int = 4) -> str:
    summaries = []
    for item in analyses[:max_sources]:
        meta = item.get("video_meta", {})
        analysis = item.get("analysis") or {}
        style = analysis.get("writing_style", {})
        structure = analysis.get("content_structure", {})
        if not style and not structure:
            continue
        summaries.append(
            f'"{meta.get("title","")}" ({meta.get("view_count",0):,} views)\n'
            f'  Tone: {style.get("tone","")}, Voice: {style.get("narrative_voice","")}, '
            f'Vocab: {style.get("vocabulary_level","")}\n'
            f'  Hook: {structure.get("hook_style","")}\n'
            f'  Pacing: {structure.get("pacing","")}\n'
            f'  Devices: {", ".join(style.get("rhetorical_devices", []))}\n'
            f'  Triggers: {", ".join(style.get("emotional_triggers", []))}'
        )
    return "\n\n".join(summaries) if summaries else "No style references loaded — write in a calm, authoritative documentary tone."


def write_script(
    research_brief: dict,
    style_analyses: list[dict],
    target_minutes: int = 10,
    narrative_voice: str = "second-person (you)",
    tone: str = "calm, intelligent, slightly philosophical",
) -> dict:
    """
    Generate a script draft from research brief + style references.
    Returns structured script dict for human review.
    """
    word_count = target_minutes * 130
    style_summary = build_style_summary(style_analyses)

    prompt = WRITER_PROMPT.format(
        research_json=json.dumps(research_brief, indent=2),
        style_summary=style_summary,
        target_minutes=target_minutes,
        word_count=word_count,
        narrative_voice=narrative_voice,
        tone=tone,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    script = json.loads(raw.strip())

    # Compute actual word count across all scenes
    total_words = sum(len(s.get("script", "").split()) for s in script.get("scenes", []))
    script["estimated_word_count"] = total_words

    return script


def print_script_preview(script: dict) -> None:
    """Print a readable preview of the script for human review."""
    scenes = script.get("scenes", [])
    print(f"\n{'='*60}")
    print(f"SCRIPT DRAFT: {script.get('title', '')}")
    print(f"{'='*60}")
    print(f"Scenes: {len(scenes)}  |  Est. words: {script.get('estimated_word_count', 0)}  "
          f"|  Target: {script.get('target_minutes', 0)} min")
    print(f"Hook choice: {script.get('hook_used', '')}\n")

    for scene in scenes:
        print(f"[{scene.get('timestamp_estimate', '')}] SCENE {scene.get('scene_number', '')}: "
              f"{scene.get('label', '').upper()}")
        print(f"  IMAGE: {scene.get('image_prompt', '')[:80]}...")
        script_preview = scene.get("script", "")[:200].replace("\n", " ")
        print(f"  SCRIPT: {script_preview}...")
        print()

    print(f"Tags: {', '.join(script.get('suggested_tags', []))}")
    print(f"Thumbnail: {script.get('thumbnail_concept', '')}")
    print(f"{'='*60}\n")
