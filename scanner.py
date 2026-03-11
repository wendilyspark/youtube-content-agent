"""
Skill 1: YouTube Scanner
Supports flexible inputs:
  - User-defined topic labels (from topics.json)
  - Free-form search queries
  - Specific YouTube video URLs
  - YouTube channel URLs or handles
"""

import re
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY, TOPICS, MAX_RESULTS_PER_QUERY, MIN_VIEW_COUNT, PUBLISHED_AFTER_DAYS


def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def build_published_after():
    if PUBLISHED_AFTER_DAYS is None:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=PUBLISHED_AFTER_DAYS)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str, max_len: int = 30) -> str:
    """Convert arbitrary text to a safe filename label."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:max_len]


# ─── Video ID / Channel ID parsers ───────────────────────────────────────────

def parse_video_id(url_or_id: str) -> str:
    """Extract video ID from a YouTube URL or return bare ID as-is."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})",
        r"youtube\.com/shorts/([\w-]{11})",
        r"youtube\.com/embed/([\w-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    # Assume it's already a bare video ID if it's 11 chars
    if re.match(r"^[\w-]{11}$", url_or_id.strip()):
        return url_or_id.strip()
    raise ValueError(f"Cannot parse video ID from: {url_or_id}")


def resolve_channel_id(youtube, url_or_handle: str) -> tuple[str, str]:
    """
    Resolve a channel URL, handle (@name), or channel ID to (channel_id, channel_name).
    Supports:
      https://www.youtube.com/@Handle
      https://www.youtube.com/channel/UCxxxx
      UCxxxx  (bare channel ID)
      @Handle (bare handle)
    """
    # Direct channel ID
    m = re.search(r"youtube\.com/channel/(UC[\w-]+)", url_or_handle)
    if m:
        cid = m.group(1)
        resp = youtube.channels().list(part="snippet", id=cid).execute()
        items = resp.get("items", [])
        name = items[0]["snippet"]["title"] if items else cid
        return cid, name

    # Handle (@name)
    handle = None
    m = re.search(r"youtube\.com/@([\w.-]+)", url_or_handle)
    if m:
        handle = m.group(1)
    elif url_or_handle.strip().startswith("@"):
        handle = url_or_handle.strip().lstrip("@")

    if handle:
        resp = youtube.channels().list(part="snippet", forHandle=handle).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"], items[0]["snippet"]["title"]
        raise ValueError(f"Channel not found for handle: @{handle}")

    # Bare UC... ID
    if url_or_handle.strip().startswith("UC"):
        cid = url_or_handle.strip()
        resp = youtube.channels().list(part="snippet", id=cid).execute()
        items = resp.get("items", [])
        name = items[0]["snippet"]["title"] if items else cid
        return cid, name

    raise ValueError(f"Cannot resolve channel from: {url_or_handle}")


# ─── Core fetch helpers ───────────────────────────────────────────────────────

def search_videos(youtube, query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[str]:
    """Search YouTube and return list of video IDs."""
    params = {
        "q": query,
        "part": "id",
        "type": "video",
        "maxResults": max_results,
        "order": "viewCount",
        "relevanceLanguage": "en",
        "videoCaption": "closedCaption",
    }
    if PUBLISHED_AFTER_DAYS:
        params["publishedAfter"] = build_published_after()
    response = youtube.search().list(**params).execute()
    return [item["id"]["videoId"] for item in response.get("items", [])]


def _parse_duration(iso: str) -> int:
    """Convert ISO 8601 duration (e.g. PT10M30S) to total seconds."""
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def get_video_details(youtube, video_ids: list[str], label: str = "", source: str = "") -> list[dict]:
    """Fetch full metadata for a list of video IDs.
    View count filter is skipped for channel/video_url sources — user chose those explicitly."""
    if not video_ids:
        return []
    response = youtube.videos().list(
        part="snippet,statistics,topicDetails,contentDetails",
        id=",".join(video_ids),
    ).execute()

    skip_view_filter = source in ("channel", "video_url")

    results = []
    for item in response.get("items", []):
        stats = item.get("statistics", {})
        view_count = int(stats.get("viewCount", 0))
        if not skip_view_filter and view_count < MIN_VIEW_COUNT:
            continue
        snippet = item["snippet"]
        duration_seconds = _parse_duration(item.get("contentDetails", {}).get("duration", ""))
        results.append({
            "video_id": item["id"],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "publish_date": snippet.get("publishedAt", ""),
            "description": snippet.get("description", "")[:500],
            "tags": snippet.get("tags", []),
            "category_id": snippet.get("categoryId", ""),
            "view_count": view_count,
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_seconds": duration_seconds,
            "topic_categories": item.get("topicDetails", {}).get("topicCategories", []),
            "label": label,
            "source": source,
        })
    return results


def get_channel_top_videos(youtube, channel_id: str, max_results: int = 20, query: str = "") -> list[str]:
    """Return video IDs from a channel, optionally filtered by a topic query.
    No caption/view filters here — applied later in get_video_details for channel scans."""
    params = {
        "part": "id",
        "channelId": channel_id,
        "type": "video",
        "order": "viewCount",
        "maxResults": max_results,
    }
    if query:
        params["q"] = query
    resp = youtube.search().list(**params).execute()
    return [item["id"]["videoId"] for item in resp.get("items", [])]


# ─── Scan modes ──────────────────────────────────────────────────────────────

def scan_topic(topic_key: str, queries: list[str] | None = None) -> tuple[str, list[dict]]:
    """
    Scan using a keyword set from topics.json (user-defined topics).
    If the topic label is not found and queries are provided, saves them to topics.json.
    Returns (label, videos).
    """
    from config import save_topics

    if topic_key not in TOPICS:
        if not queries:
            raise ValueError(
                f"Unknown topic '{topic_key}' and no queries provided. "
                f"Available: {list(TOPICS.keys())}"
            )
        TOPICS[topic_key] = queries
        save_topics(TOPICS)
        print(f"  New topic '{topic_key}' saved to topics.json ({len(queries)} queries).")

    youtube = get_youtube_client()
    seen_ids = set()
    all_videos = []

    for query in TOPICS[topic_key]:
        print(f"  Searching: '{query}'...")
        try:
            ids = search_videos(youtube, query)
            videos = get_video_details(youtube, ids, label=topic_key, source="topic")
            for v in videos:
                if v["video_id"] not in seen_ids:
                    seen_ids.add(v["video_id"])
                    v["search_query"] = query
                    all_videos.append(v)
        except Exception as e:
            print(f"  Warning: failed query '{query}': {e}")

    all_videos.sort(key=lambda x: x["view_count"], reverse=True)
    return topic_key, all_videos


def scan_query(query: str, label: str | None = None) -> tuple[str, list[dict]]:
    """
    Scan using a free-form search query string.
    Returns (label, videos).
    """
    effective_label = label or slugify(query)
    youtube = get_youtube_client()
    print(f"  Searching: '{query}'...")
    ids = search_videos(youtube, query, max_results=MAX_RESULTS_PER_QUERY * 2)
    videos = get_video_details(youtube, ids, label=effective_label, source="query")
    for v in videos:
        v["search_query"] = query
    videos.sort(key=lambda x: x["view_count"], reverse=True)
    return effective_label, videos


def scan_video_urls(urls: list[str], label: str | None = None) -> tuple[str, list[dict]]:
    """
    Fetch metadata for specific YouTube video URLs.
    Returns (label, videos).
    """
    youtube = get_youtube_client()
    video_ids = []
    for url in urls:
        try:
            video_ids.append(parse_video_id(url))
        except ValueError as e:
            print(f"  Warning: {e}")

    if not video_ids:
        raise ValueError("No valid video IDs found in provided URLs.")

    effective_label = label or (f"video_{video_ids[0]}" if len(video_ids) == 1 else "videos_custom")
    # For direct video fetches, skip the MIN_VIEW_COUNT filter
    response = get_youtube_client().videos().list(
        part="snippet,statistics,topicDetails",
        id=",".join(video_ids),
    ).execute()

    videos = []
    for item in response.get("items", []):
        stats = item.get("statistics", {})
        snippet = item["snippet"]
        videos.append({
            "video_id": item["id"],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "publish_date": snippet.get("publishedAt", ""),
            "description": snippet.get("description", "")[:500],
            "tags": snippet.get("tags", []),
            "category_id": snippet.get("categoryId", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "topic_categories": item.get("topicDetails", {}).get("topicCategories", []),
            "label": effective_label,
            "source": "video_url",
        })
    return effective_label, videos


def scan_channel(channel_url: str, label: str | None = None, max_results: int = 15, query: str = "") -> tuple[str, list[dict]]:
    """
    Fetch top videos from a YouTube channel URL, handle, or ID.
    Optionally filter by topic query within the channel.
    Returns (label, videos).
    """
    youtube = get_youtube_client()
    channel_id, channel_name = resolve_channel_id(youtube, channel_url)
    effective_label = label or f"channel_{slugify(channel_name)}"

    print(f"  Channel resolved: {channel_name} ({channel_id})")
    if query:
        print(f"  Filtering by topic: '{query}'")
    print(f"  Fetching top {max_results} videos...")

    video_ids = get_channel_top_videos(youtube, channel_id, max_results, query=query)
    videos = get_video_details(youtube, video_ids, label=effective_label, source="channel")
    for v in videos:
        v["channel_source"] = channel_name
        if query:
            v["topic_filter"] = query
    videos.sort(key=lambda x: x["view_count"], reverse=True)
    return effective_label, videos
