"""
Agent 4: Director Agent
Takes approved script → enriches each scene with production-ready
image prompts, pacing notes, and caption timing plan.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, IMAGE_STYLE_PRESET

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DIRECTOR_PROMPT = """You are a visual director for a psychology and consciousness YouTube channel that produces cinematic slide-based video essays.

Given this approved script, enhance each scene with:
1. A refined, production-ready image generation prompt (Stable Diffusion style)
2. Visual mood and color palette for the scene
3. Pacing notes for the voiceover delivery
4. Any on-screen text suggestions (beyond captions)

APPROVED SCRIPT:
{script_json}

IMAGE STYLE CONTEXT: {style_preset} style, 16:9 landscape, psychological/symbolic/cinematic
Avoid: faces that look like real people, text in images, watermarks

Return ONLY valid JSON — same scenes array with added fields per scene:
{{
  "title": "same title",
  "scenes": [
    {{
      "scene_number": 1,
      "label": "same label",
      "timestamp_estimate": "same",
      "script": "same script text — do not change",
      "image_prompt": "Refined, detailed Stable Diffusion prompt. Include: subject, mood, lighting, color palette, style. Example: 'A lone figure standing at the edge of a mirror-smooth lake at dusk, their reflection distorted into shadow, dramatic chiaroscuro lighting, deep indigo and amber tones, cinematic, symbolic, ultra-detailed'",
      "image_negative_prompt": "ugly, blurry, text, watermark, realistic faces, crowded, noisy",
      "color_palette": ["#hex1", "#hex2", "#hex3"],
      "mood": "one-word mood descriptor",
      "pacing_note": "Delivery instruction for the voiceover artist, e.g. 'slow and deliberate, pause after first sentence'",
      "onscreen_text": "Optional bold text to show on screen at this moment, or null"
    }}
  ],
  "visual_throughline": "The consistent visual motif/theme running through all scenes",
  "color_story": "Overall color palette evolution across the video"
}}"""


def direct_script(script: dict) -> dict:
    """
    Enrich an approved script with full production direction.
    """
    prompt = DIRECTOR_PROMPT.format(
        script_json=json.dumps(script, indent=2),
        style_preset=IMAGE_STYLE_PRESET,
    )

    import re
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    directed = json.loads(raw.strip())

    # Preserve top-level fields from original script that Director doesn't return
    for key in ("hook_used", "target_minutes", "estimated_word_count", "suggested_tags", "thumbnail_concept"):
        if key in script and key not in directed:
            directed[key] = script[key]

    return directed


def print_shot_list(directed: dict) -> None:
    """Print a readable shot list for human review."""
    scenes = directed.get("scenes", [])
    print(f"\n{'='*60}")
    print(f"SHOT LIST: {directed.get('title', '')}")
    print(f"Visual throughline: {directed.get('visual_throughline', '')}")
    print(f"Color story: {directed.get('color_story', '')}")
    print(f"{'='*60}")

    for s in scenes:
        print(f"\n[Scene {s.get('scene_number')}] {s.get('label','').upper()} — {s.get('timestamp_estimate','')}")
        print(f"  Mood: {s.get('mood','')}  |  Palette: {' '.join(s.get('color_palette',[]))}")
        print(f"  Image: {s.get('image_prompt','')[:100]}...")
        print(f"  Pacing: {s.get('pacing_note','')}")
        if s.get("onscreen_text"):
            print(f"  On-screen text: \"{s.get('onscreen_text')}\"")

    print(f"\n{'='*60}\n")
