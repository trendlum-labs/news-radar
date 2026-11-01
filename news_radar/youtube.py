"""Small, dependency-free client for YouTube Data API v3.

Absence from search results is NOT evidence that no matching video exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeAPIError(RuntimeError):
    """A YouTube API request failed."""


class YouTubeClient:
    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: int = 15,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("YOUTUBE_API_KEY is required")
        self._api_key = api_key.strip()
        self._timeout = timeout_seconds
        self._open = opener or urlopen

    def _get(self, endpoint: str, params: dict[str, str | int]) -> dict[str, Any]:
        # Never log the request URL: it contains the API key.
        url = f"{endpoint}?{urlencode({**params, 'key': self._api_key})}"
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with self._open(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except HTTPError as error:
            message = "request rejected"
            try:
                body = json.loads(error.read().decode("utf-8"))
                message = str(body.get("error", {}).get("message", message))
            except (ValueError, UnicodeDecodeError, AttributeError):
                pass
            # Do not propagate error.url or raw HTTPError string (may expose key).
            raise YouTubeAPIError(f"YouTube API HTTP {error.code}: {message}") from None
        except (URLError, TimeoutError):
            raise YouTubeAPIError("YouTube API network request failed") from None
        except (ValueError, UnicodeDecodeError):
            raise YouTubeAPIError("YouTube API returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise YouTubeAPIError("YouTube API returned an unexpected response")
        return payload

    def search_videos(
        self,
        query: str,
        *,
        hours: float = 48,
        order: str = "relevance",
        max_results: int = 50,
        language: str | None = None,
        region: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        if not 0 < hours <= 24 * 365:
            raise ValueError("hours must be between 0 and 8760")
        if order not in {"relevance", "date"}:
            raise ValueError("order must be relevance or date")
        if not 1 <= max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")

        at = now or datetime.now(timezone.utc)
        if at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        at = at.astimezone(timezone.utc)
        since = at - timedelta(hours=hours)
        params: dict[str, str | int] = {
            "part": "snippet",
            "type": "video",
            "q": query.strip(),
            "order": order,
            "maxResults": max_results,
            "publishedAfter": since.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        if language:
            params["relevanceLanguage"] = language
        if region:
            params["regionCode"] = region.upper()
        response = self._get(SEARCH_URL, params)
        videos: list[dict[str, Any]] = []
        for item in response.get("items", []):
            if not isinstance(item, dict):
                continue
            video_id = item.get("id", {}).get("videoId") if isinstance(item.get("id"), dict) else None
            snippet = item.get("snippet") or {}
            if not video_id or not isinstance(snippet, dict):
                continue
            videos.append({
                "id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt"),
            })
        return {
            "query": query.strip(),
            "order": order,
            "searched_at": at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "published_after": params["publishedAfter"],
            "returned_count": len(videos),
            "next_page_available": bool(response.get("nextPageToken")),
            "videos": videos,
        }

    def videos_by_id(self, video_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = list(dict.fromkeys(x.strip() for x in video_ids if x.strip()))
        if not ids:
            return {}
        if len(ids) > 50:
            raise ValueError("videos_by_id accepts at most 50 IDs per request")
        response = self._get(VIDEOS_URL, {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(ids),
        })
        videos: dict[str, dict[str, Any]] = {}
        for item in response.get("items", []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            snippet = item.get("snippet") or {}
            statistics = item.get("statistics") or {}
            content = item.get("contentDetails") or {}
            videos[item["id"]] = {
                "id": item["id"],
                "title": snippet.get("title"),
                "channel": snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "duration": content.get("duration"),
                "view_count": statistics.get("viewCount"),
            }
        return videos


def compare_search_orders(
    client: YouTubeClient,
    query: str,
    *,
    expected_ids: list[str] | None = None,
    hours: float = 48,
    max_results: int = 50,
    language: str | None = None,
    region: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Two search calls, plus one videos.list call if expected IDs are supplied.

    An absent ID means only that it was not returned in these two result pages.
    """
    at = now or datetime.now(timezone.utc)
    expected_ids = list(dict.fromkeys(expected_ids or []))
    if len(expected_ids) > 50:
        raise ValueError("At most 50 expected video IDs are supported")
    kwargs = dict(hours=hours, max_results=max_results, language=language, region=region, now=at)
    relevance = client.search_videos(query, order="relevance", **kwargs)
    recent = client.search_videos(query, order="date", **kwargs)
    relevance_ids = {item["id"] for item in relevance["videos"]}
    recent_ids = {item["id"] for item in recent["videos"]}
    known_videos = client.videos_by_id(expected_ids) if expected_ids else {}
    since = at.astimezone(timezone.utc) - timedelta(hours=hours)

    expected = []
    for video_id in expected_ids:
        video = known_videos.get(video_id)
        within_window = None
        if video and video.get("published_at"):
            try:
                published = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
                within_window = since <= published <= at
            except ValueError:
                pass
        expected.append({
            "id": video_id,
            "available_via_videos_list": video is not None,
            "within_requested_window": within_window,
            "in_relevance_first_page": video_id in relevance_ids,
            "in_date_first_page": video_id in recent_ids,
            "metadata": video,
        })

    return {
        "query": query,
        "searched_at": at.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "search_calls": 2,
        "video_detail_calls": 1 if expected_ids else 0,
        "relevance": relevance,
        "date": recent,
        "overlap_count": len(relevance_ids & recent_ids),
        "only_relevance_count": len(relevance_ids - recent_ids),
        "only_date_count": len(recent_ids - relevance_ids),
        "expected_videos": expected,
        "limitation": "Results cover only the first page of each order. Missing IDs do not prove a video is absent from YouTube or unindexed.",
    }
