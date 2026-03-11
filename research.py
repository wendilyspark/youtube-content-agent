"""
Agent 2: Research Agent
Given a user topic + optional angle, produces a deep content brief
that the Writer Agent uses to generate the script.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

RESEARCH_PROMPT = """You are a deep researcher with broad expertise across many fields. You write for a general but intellectually curious audience.

The user wants to create a video on the following topic:

TOPIC: {topic}
PERSONAL ANGLE / THEME (if provided): {angle}
RELATED NICHE: {niche}

Your task: produce a rich content research brief that a scriptwriter can use to build a compelling, original video.

Return ONLY valid JSON with this structure:
{{
  "topic": "{topic}",
  "core_question": "The central question this video answers for the viewer",
  "hook_angles": [
    "A surprising fact or counterintuitive angle to open with",
    "A relatable scenario or emotional pain point",
    "A provocative question to pose"
  ],
  "key_concepts": [
    {{
      "concept": "Concept name",
      "explanation": "Plain-language explanation (2-3 sentences)",
      "depth_level": "foundational | intermediate | advanced"
    }}
  ],
  "narrative_arc": {{
    "problem_setup": "How to frame the viewer's problem or curiosity",
    "journey": "The intellectual/emotional journey the video takes",
    "resolution": "The insight or transformation the viewer leaves with"
  }},
  "supporting_material": [
    {{
      "type": "quote | study | example | metaphor | story",
      "content": "The actual material",
      "source": "Author, book, or study name if applicable"
    }}
  ],
  "viewer_transformation": "What does the viewer think/feel/understand differently after watching?",
  "content_warnings": "Any nuances to handle carefully (e.g. trauma-related topics)",
  "suggested_sections": [
    {{
      "title": "Section name",
      "purpose": "What this section achieves",
      "key_point": "The main thing to say here"
    }}
  ],
  "seo_keywords": ["keyword1", "keyword2"],
  "suggested_video_title": "A compelling YouTube title"
}}"""


def research_topic(topic: str, angle: str = "", niche: str = "") -> dict:
    """
    Research a topic and return a structured content brief.

    Args:
        topic: Main topic (e.g. "the Jungian shadow in relationships")
        angle: Your personal angle or theme (e.g. "how shadow drives attraction patterns")
        niche: Which niche this falls under (default: psychology & consciousness)
    """
    prompt = RESEARCH_PROMPT.format(topic=topic, angle=angle or "not specified", niche=niche)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    import re
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw.strip())


def print_brief_summary(brief: dict) -> None:
    """Print a human-readable summary of the research brief."""
    print(f"\n{'='*60}")
    print(f"RESEARCH BRIEF: {brief.get('topic', '')}")
    print(f"{'='*60}")
    print(f"Core question: {brief.get('core_question', '')}")
    print(f"Suggested title: {brief.get('suggested_video_title', '')}")
    print(f"\nHook angles:")
    for h in brief.get("hook_angles", []):
        print(f"  • {h}")
    print(f"\nKey concepts ({len(brief.get('key_concepts', []))}):")
    for c in brief.get("key_concepts", []):
        print(f"  • {c['concept']} [{c['depth_level']}]")
    print(f"\nSections ({len(brief.get('suggested_sections', []))}):")
    for s in brief.get("suggested_sections", []):
        print(f"  • {s['title']}: {s['purpose']}")
    print(f"\nViewer transformation:")
    print(f"  {brief.get('viewer_transformation', '')}")
    print(f"{'='*60}\n")
