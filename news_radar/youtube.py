"""YouTube Data API search for recent news coverage."""

from datetime import datetime, timedelta, timezone
from os import getenv
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json


def search_videos(
    query: str,
    *,
    api_key: str | None = None,
    hours: int = 24,
    max_results: int = 50,
    order: str = "date",
    language: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """Find recent videos about an event. Missing results do not prove no videos exist."""
    key = api_key or getenv("YOUTUBE_API_KEY")
    if not key:
        raise ValueError("YOUTUBE_API_KEY is required")
    if not query.strip():
        raise ValueError("query cannot be empty")
    if hours <= 0 or not 1 <= max_results <= 50 or order not in {"date", "relevance"}:
        raise ValueError("invalid search parameters")

    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours))
    params = {
        "key": key,
        "part": "snippet",
        "type": "video",
        "q": query.strip(),
        "order": order,
        "maxResults": max_results,
        "publishedAfter": published_after.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if language:
        params["relevanceLanguage"] = language
    if region:
        params["regionCode"] = region.upper()

    url = "https://www.googleapis.com/youtube/v3/search?" + urlencode(params)
    try:
        with urlopen(url, timeout=15) as response:
            data = json.load(response)
    except HTTPError as error:
        # Never expose error.url: the URL contains the API key.
        raise RuntimeError(f"YouTube API returned HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("YouTube API request failed") from None

    videos = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        videos.append({
            "id": video_id,
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt"),
            "description": snippet.get("description", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return videos
