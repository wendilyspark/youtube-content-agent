"""
Agent 5: Media Agent
Given a directed script:
  1. Generates AI images per scene (Stability AI)
  2. Generates voiceover per scene (ElevenLabs) with word-level timestamps
  3. Assembles video: image + audio + synced captions → MP4
"""

import os
import json
import time
import requests
from pathlib import Path
from config import (
    ELEVENLABS_API_KEY, STABILITY_API_KEY,
    DEFAULT_VOICE_ID, DEFAULT_VOICE_MODEL,
    STABILITY_IMAGE_MODEL, IMAGE_ASPECT_RATIO,
    PROJECTS_DIR,
)

EL_BASE = "https://api.elevenlabs.io/v1"
STABILITY_BASE = "https://api.stability.ai/v2beta"
EL_HEADERS = {"xi-api-key": ELEVENLABS_API_KEY}

# Color theme prompt additions — appended to each image prompt when selected
COLOR_THEMES = {
    "dark_mysterious": "dark navy and charcoal, deep shadows, silver highlights, brooding mysterious atmosphere",
    "warm_golden":     "warm golden amber light, candlelight glow, copper and honey tones, warm cinematic",
    "ethereal":        "soft white and pale blue, misty ethereal light, silver luminescence, dreamlike airy",
    "earth_forest":    "deep forest green, earthy brown and ochre, natural organic textures, grounded",
    "cosmic":          "deep space indigo and violet, cosmic nebula tones, starlight, vast and infinite",
    "sunset":          "warm sunset orange and coral, rose gold, pink and amber sky tones, golden hour",
    "monochrome":      "black and white, high contrast monochrome, dramatic shadows and highlights, timeless",
}


# ─── Image Generation ────────────────────────────────────────────────────────

def generate_image(prompt: str, negative_prompt: str, output_path: str,
                   style_preset: str = None, color_theme_prompt: str = "") -> str:
    """Generate one image via Stability AI. Returns saved file path."""
    url = f"{STABILITY_BASE}/{STABILITY_IMAGE_MODEL}"
    full_prompt = f"{prompt}, {color_theme_prompt}" if color_theme_prompt else prompt
    # Stability AI requires multipart/form-data — use files= param
    files = {
        "prompt": (None, full_prompt),
        "negative_prompt": (None, negative_prompt or "ugly, blurry, text, watermark, distorted"),
        "aspect_ratio": (None, IMAGE_ASPECT_RATIO),
        "output_format": (None, "jpeg"),
    }
    if style_preset:
        files["style_preset"] = (None, style_preset)
    headers = {
        "authorization": f"Bearer {STABILITY_API_KEY}",
        "accept": "image/*",
    }
    resp = requests.post(url, headers=headers, files=files)
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(resp.content)
    return output_path


def generate_all_images(scenes: list[dict], project_dir: str,
                        style_preset: str = None, color_theme_prompt: str = "") -> list[str]:
    """Generate images for all scenes. Returns list of image paths. Skips existing files."""
    img_dir = os.path.join(project_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    paths = []

    for scene in scenes:
        n = scene["scene_number"]
        out_path = os.path.join(img_dir, f"scene_{n:02d}.jpg")
        if os.path.exists(out_path):
            print(f"  Scene {n} image already exists — skipping.")
            paths.append(out_path)
            continue
        print(f"  Generating image for scene {n}: {scene.get('label','')}...")
        try:
            generate_image(
                prompt=scene.get("image_prompt", "cinematic abstract visual"),
                negative_prompt=scene.get("image_negative_prompt", ""),
                output_path=out_path,
                style_preset=style_preset,
                color_theme_prompt=color_theme_prompt,
            )
            paths.append(out_path)
            time.sleep(0.5)  # brief pause to respect rate limits
        except Exception as e:
            print(f"  Image generation failed for scene {n}: {e}")
            paths.append(None)

    return paths


# ─── Voiceover + Caption Timestamps ──────────────────────────────────────────

def generate_voiceover_with_timestamps(
    text: str,
    voice_id: str,
    output_path: str,
) -> tuple[str, list[dict]]:
    """
    Generate voiceover audio + word-level timestamps via ElevenLabs.
    Returns (audio_path, word_timestamps).
    word_timestamps: list of {word, start, end} in seconds.
    """
    url = f"{EL_BASE}/text-to-speech/{voice_id}/with-timestamps"
    payload = {
        "text": text,
        "model_id": DEFAULT_VOICE_MODEL,
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.2},
    }
    resp = requests.post(
        url,
        headers={**EL_HEADERS, "Content-Type": "application/json"},
        json=payload,
    )
    resp.raise_for_status()
    data = resp.json()

    # Save audio
    import base64
    audio_bytes = base64.b64decode(data["audio_base64"])
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    # Extract word-level timestamps
    alignment = data.get("alignment", {})
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    # Group characters into words
    word_timestamps = _chars_to_words(chars, starts, ends)
    return output_path, word_timestamps


def _chars_to_words(chars: list, starts: list, ends: list) -> list[dict]:
    """Convert character-level timestamps to word-level."""
    words = []
    current_word = []
    word_start = None
    word_end = None

    for char, start, end in zip(chars, starts, ends):
        if char == " " or char == "\n":
            if current_word:
                words.append({
                    "word": "".join(current_word),
                    "start": word_start,
                    "end": word_end,
                })
                current_word = []
                word_start = None
        else:
            if not current_word:
                word_start = start
            current_word.append(char)
            word_end = end

    if current_word:
        words.append({"word": "".join(current_word), "start": word_start, "end": word_end})

    return words


def generate_all_voiceovers(
    scenes: list[dict],
    voice_id: str,
    project_dir: str,
) -> list[tuple[str, list[dict]]]:
    """Generate voiceover + timestamps for all scenes. Skips if audio+timestamps already exist."""
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    results = []

    for scene in scenes:
        n = scene["scene_number"]
        text = scene.get("script", "").replace("[PAUSE]", "...")
        out_path = os.path.join(audio_dir, f"scene_{n:02d}.mp3")
        ts_path  = os.path.join(audio_dir, f"scene_{n:02d}_timestamps.json")

        if os.path.exists(out_path) and os.path.exists(ts_path):
            print(f"  Scene {n} audio already exists — loading saved timestamps.")
            with open(ts_path) as f:
                timestamps = json.load(f)
            results.append((out_path, timestamps))
            continue

        print(f"  Generating voiceover for scene {n}: {scene.get('label','')}...")
        try:
            audio_path, timestamps = generate_voiceover_with_timestamps(text, voice_id, out_path)
            # Save timestamps so we can resume without re-calling the API
            with open(ts_path, "w") as f:
                json.dump(timestamps, f)
            results.append((audio_path, timestamps))
        except Exception as e:
            print(f"  Voiceover failed for scene {n}: {e}")
            results.append((None, []))

    return results


# ─── Caption Splitting ───────────────────────────────────────────────────────

def split_captions_by_punctuation(words: list[dict], max_words: int = 10) -> list[tuple]:
    """
    Split word-timestamp list into caption chunks at natural language boundaries.
    Returns list of (start_sec, end_sec, text) tuples.
    Breaks at: . ? ! (always), , (if ≥5 words accumulated), — ... tokens (always flush).
    """
    chunks, chunk, start = [], [], None

    def flush():
        nonlocal chunk, start
        if chunk:
            chunks.append((start, chunk[-1]["end"], " ".join(x["word"] for x in chunk)))
        chunk, start = [], None

    for w in words:
        word = w["word"]
        if start is None:
            start = w["start"]
        if word in ("...", "—"):
            if chunk:
                flush()
            continue
        chunk.append(w)
        last = word[-1] if word else ""
        if last in (".", "?", "!"):
            flush()
        elif last == "," and len(chunk) >= 5:
            flush()
        elif len(chunk) >= max_words:
            flush()

    if chunk:
        flush()
    return chunks


# ─── Fast Video Renderer (Pillow + ffmpeg pipe) ───────────────────────────────

def render_scenes_to_video(
    scene_numbers: list[int],
    project_dir: str,
    output_path: str,
    fps: int = 25,
    resolution: tuple = (1920, 1080),
    caption_font_size: int = 68,
    caption_shadow_color: tuple = (0, 0, 0),
    ken_burns_zoom: float = 1.25,
    caption_y_ratio: float = 0.72,
) -> str:
    """
    Render specific scenes to MP4 using Pillow (Ken Burns + captions) piped to ffmpeg.
    Faster and more stable than MoviePy. Reuses existing images and audio from project_dir.

    Args:
        scene_numbers:        e.g. [1, 2, 3] — images + audio must already exist
        project_dir:          project folder with images/ and audio/ subdirs
        output_path:          where to save the output MP4
        caption_shadow_color: RGB tuple for caption outline, e.g. (20, 45, 55) for dark teal
        ken_burns_zoom:       final zoom level (1.0 = no zoom, 1.25 = 25% zoom-in over scene)
        caption_y_ratio:      vertical position of caption center (0.72 = lower third)
    Returns:
        output_path
    """
    import subprocess
    import textwrap
    from PIL import Image, ImageDraw, ImageFont

    W, H = resolution

    # Load bold font — try Arial Bold, fall back to Helvetica
    for font_path in ("/Library/Fonts/Arial Bold.ttf",
                      "/System/Library/Fonts/Helvetica.ttc"):
        try:
            font = ImageFont.truetype(font_path, caption_font_size)
            break
        except Exception:
            font = ImageFont.load_default()

    # Step 1: concatenate audio for all scenes
    audio_dir   = os.path.join(project_dir, "audio")
    concat_list = os.path.join(audio_dir, "_concat_list.txt")
    concat_mp3  = os.path.join(audio_dir, "_concat_temp.mp3")

    with open(concat_list, "w") as f:
        for n in scene_numbers:
            ap = os.path.join(audio_dir, f"scene_{n:02d}.mp3")
            if not os.path.exists(ap):
                raise FileNotFoundError(f"Audio missing for scene {n}: {ap}")
            f.write(f"file '{ap}'\n")

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", concat_mp3],
        check=True, capture_output=True,
    )

    # Step 2: pipe video frames to ffmpeg
    proc = subprocess.Popen(
        ["ffmpeg", "-y",
         "-f", "rawvideo", "-vcodec", "rawvideo",
         "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(fps), "-i", "pipe:0",
         "-i", concat_mp3,
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-c:a", "aac", "-b:a", "192k",
         "-pix_fmt", "yuv420p", "-shortest",
         output_path],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )

    for n in scene_numbers:
        img_path = os.path.join(project_dir, "images", f"scene_{n:02d}.jpg")
        ts_path  = os.path.join(audio_dir, f"scene_{n:02d}_timestamps.json")
        ap       = os.path.join(audio_dir, f"scene_{n:02d}.mp3")

        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Image missing for scene {n}: {img_path}")

        # Load captions (gracefully skip if timestamps missing)
        chunks = []
        if os.path.exists(ts_path):
            with open(ts_path) as f:
                chunks = split_captions_by_punctuation(json.load(f))

        def caption_at(t, _c=chunks):
            for s, e, text in _c:
                if s <= t < e:
                    return text
            return None

        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", ap],
            capture_output=True, text=True, check=True,
        )
        duration     = float(r.stdout.strip())
        total_frames = int(duration * fps) + 1

        base       = Image.open(img_path).convert("RGB")
        bW, bH     = base.size
        zoom_range = ken_burns_zoom - 1.0

        print(f"  Rendering scene {n}: {duration:.1f}s ({total_frames} frames)...")

        for i in range(total_frames):
            t    = i / fps
            zoom = 1.0 + zoom_range * (t / max(duration - 1 / fps, 1))
            cw, ch = bW / zoom, bH / zoom
            crop   = base.crop((bW / 2 - cw / 2, bH / 2 - ch / 2,
                                 bW / 2 + cw / 2, bH / 2 + ch / 2))
            frame  = crop.resize((W, H), Image.LANCZOS)

            text = caption_at(t)
            if text:
                draw  = ImageDraw.Draw(frame)
                lines = textwrap.wrap(text, width=36)
                lh    = caption_font_size + 16
                y     = int(H * caption_y_ratio) - (len(lines) * lh) // 2
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    x    = (W - (bbox[2] - bbox[0])) // 2
                    # Thick stroke for legibility
                    for dx, dy in [(-4,0),(4,0),(0,-4),(0,4),
                                   (-3,-3),(3,-3),(-3,3),(3,3),
                                   (-4,-4),(4,-4),(-4,4),(4,4)]:
                        draw.text((x + dx, y + dy), line, font=font,
                                  fill=caption_shadow_color)
                    draw.text((x, y), line, font=font, fill=(255, 255, 255))
                    y += lh

            proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()

    # Clean up temp concat files
    for tmp in (concat_mp3, concat_list):
        try:
            os.unlink(tmp)
        except Exception:
            pass

    return output_path


# ─── Full Pipeline ────────────────────────────────────────────────────────────

def produce_video(directed_script: dict, voice_id: str = DEFAULT_VOICE_ID,
                  project_dir: str = None, style_preset: str = None,
                  color_theme: str = None) -> str:
    """
    Full media production pipeline for an approved, directed script.
    Returns path to final MP4.
    Pass project_dir to resume a partially-completed run (reuses existing images/audio).
    Pass style_preset (e.g. 'cinematic') and color_theme (e.g. 'dark_mysterious') for visual style.
    """
    title = directed_script.get("title", "video")
    scenes = directed_script.get("scenes", [])

    # Resolve color theme to prompt text
    color_theme_prompt = COLOR_THEMES.get(color_theme, "") if color_theme else ""
    if style_preset:
        print(f"  Image style: {style_preset}")
    if color_theme_prompt:
        print(f"  Color theme: {color_theme} → {color_theme_prompt}")

    # Create (or reuse) project folder
    if not project_dir:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.replace(" ", "_")[:30]
        project_dir = os.path.join(PROJECTS_DIR, f"{safe_title}_{timestamp}")
    os.makedirs(project_dir, exist_ok=True)

    # Save directed script into project
    with open(os.path.join(project_dir, "directed_script.json"), "w") as f:
        json.dump(directed_script, f, indent=2)

    print(f"\nProject folder: {project_dir}")
    print(f"Scenes to produce: {len(scenes)}\n")

    print("Step 1/3: Generating images...")
    image_paths = generate_all_images(scenes, project_dir,
                                      style_preset=style_preset,
                                      color_theme_prompt=color_theme_prompt)

    print("\nStep 2/3: Generating voiceovers...")
    voiceover_results = generate_all_voiceovers(scenes, voice_id, project_dir)

    print("\nStep 3/3: Assembling video...")
    # Only render scenes that have both image and audio
    scene_numbers = []
    for scene, img_path, (audio_path, _) in zip(scenes, image_paths, voiceover_results):
        if img_path and audio_path:
            scene_numbers.append(scene["scene_number"])

    safe_title = title.replace(" ", "_").replace("/", "-")[:40]
    out_path = os.path.join(project_dir, f"{safe_title}.mp4")
    final_path = render_scenes_to_video(scene_numbers, project_dir, out_path)

    print(f"\nDone! Final video: {final_path}")
    return final_path
