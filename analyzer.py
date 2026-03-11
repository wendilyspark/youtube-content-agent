"""
Skill 3: Content Analyzer (Claude-powered)
Analyzes transcripts to extract structure, main points, style, and tags.
"""

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


ANALYSIS_PROMPT = """You are an expert content analyst specializing in psychology, spirituality, and self-development YouTube content.

Analyze the following YouTube video transcript and metadata, then return a structured JSON analysis.

VIDEO METADATA:
Title: {title}
Channel: {channel}
Topic Category: {topic}
Tags: {tags}
View Count: {view_count:,}

TRANSCRIPT (first 8000 chars):
{transcript_excerpt}

Return ONLY valid JSON with this exact structure:
{{
  "content_structure": {{
    "hook_style": "description of how the video opens and grabs attention",
    "intro_pattern": "how the intro is structured",
    "main_sections": ["section 1 description", "section 2 description", "..."],
    "storytelling_devices": ["device 1", "device 2"],
    "call_to_action": "how the video ends / what viewer is asked to do",
    "pacing": "fast/moderate/slow - describe the pacing style"
  }},
  "main_points": [
    "Point 1: concise description",
    "Point 2: concise description"
  ],
  "writing_style": {{
    "tone": "authoritative/conversational/inspirational/academic/etc",
    "vocabulary_level": "basic/intermediate/advanced",
    "narrative_voice": "first-person/second-person/third-person",
    "recurring_phrases": ["phrase 1", "phrase 2"],
    "rhetorical_devices": ["device 1", "device 2"],
    "emotional_triggers": ["curiosity/fear/hope/etc"]
  }},
  "topic_analysis": {{
    "primary_topic": "specific topic",
    "subtopics": ["subtopic 1", "subtopic 2"],
    "psychological_concepts": ["concept 1", "concept 2"],
    "target_audience": "who this video is made for",
    "knowledge_level_required": "beginner/intermediate/advanced"
  }},
  "suggested_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "engagement_factors": ["what makes this video compelling or successful"],
  "content_gaps": ["topics briefly mentioned but not explored - opportunity for your own videos"]
}}"""


def analyze_video(video_meta: dict, transcript_data: dict) -> dict:
    """
    Send video metadata + transcript to Claude for analysis.
    Returns structured analysis dict.
    """
    transcript_excerpt = transcript_data.get("full_text", "")[:8000]

    prompt = ANALYSIS_PROMPT.format(
        title=video_meta.get("title", ""),
        channel=video_meta.get("channel", ""),
        topic=video_meta.get("topic", ""),
        tags=", ".join(video_meta.get("tags", [])[:20]),
        view_count=video_meta.get("view_count", 0),
        transcript_excerpt=transcript_excerpt,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    import json, re
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw.strip())


def analyze_batch(videos_with_transcripts: list[dict]) -> list[dict]:
    """
    Analyze a list of dicts: {video_meta, transcript_data}.
    Returns enriched list with 'analysis' key added.
    """
    results = []
    for i, item in enumerate(videos_with_transcripts, 1):
        meta = item["video_meta"]
        transcript = item["transcript_data"]
        print(f"  Analyzing [{i}/{len(videos_with_transcripts)}]: {meta.get('title', '')[:60]}...")
        try:
            analysis = analyze_video(meta, transcript)
            results.append({**item, "analysis": analysis})
        except Exception as e:
            print(f"  Analysis failed: {e}")
            results.append({**item, "analysis": None})
    return results
