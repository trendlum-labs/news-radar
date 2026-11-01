"""Search recent YouTube videos and filter by actual duration."""

import json
import re
from datetime import datetime, timedelta, timezone
from os import getenv
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def _key_from_dotenv() -> str | None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "YOUTUBE_API_KEY":
            return value.strip().strip('"').strip("'") or None
    return None


def _get(endpoint: str, params: dict) -> dict:
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urlencode(params)
    try:
        with urlopen(url, timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        # Don't expose the URL, which contains the API key.
        raise RuntimeError(f"YouTube API returned HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("YouTube API request failed") from None


def _duration_seconds(duration: str) -> int | None:
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return None
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def search_videos(
    query: str,
    *,
    api_key: str | None = None,
    hours: int = 24,
    max_results: int = 50,
    order: str = "date",
    language: str | None = None,
    region: str | None = None,
    long_form: bool = True,
) -> list[dict]:
    """One search; one videos.list to retrieve durations. Long form is >= 4 min."""
    key = api_key or getenv("YOUTUBE_API_KEY") or _key_from_dotenv()
    if not key:
        raise ValueError("YOUTUBE_API_KEY is required")
    if not query.strip():
        raise ValueError("query cannot be empty")
    if hours <= 0 or not 1 <= max_results <= 50 or order not in {"date", "relevance"}:
        raise ValueError("invalid search parameters")

    params = {
        "key": key,
        "part": "snippet",
        "type": "video",
        "q": query.strip(),
        "order": order,
        "maxResults": max_results,
        "publishedAfter": (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if language:
        params["relevanceLanguage"] = language
    if region:
        params["regionCode"] = region.upper()

    results = _get("search", params)
    videos = []
    for item in results.get("items", []):
        video_id = (item.get("id") or {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet") or {}
        videos.append({
            "id": video_id,
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt"),
            "description": snippet.get("description", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    if not videos:
        return []

    details = _get("videos", {
        "key": key,
        "part": "contentDetails",
        "id": ",".join(video["id"] for video in videos),
    })
    durations = {
        item["id"]: _duration_seconds((item.get("contentDetails") or {}).get("duration", ""))
        for item in details.get("items", [])
    }

    for video in videos:
        video["duration_seconds"] = durations.get(video["id"])

    if long_form:
        return [v for v in videos if v["duration_seconds"] is not None and v["duration_seconds"] >= 240]
    return videos
