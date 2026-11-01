"""Google Trends Trending Now via Google's internal backend."""

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _utc(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def get_trends(country: str = "US", hours: int = 4) -> list[dict]:
    """Get all Trending Now results for a country in Google's native time window."""
    if not isinstance(country, str) or len(country.strip()) != 2 or not country.strip().isascii() or not country.strip().isalpha():
        raise ValueError("country must be a two-letter country code")
    if type(hours) is not int or hours not in (4, 24, 48, 168):
        raise ValueError("hours must be 4, 24, 48 or 168")

    country = country.strip().upper()
    args = json.dumps([None, None, country, 0, "en-US", hours, 1])
    payload = json.dumps([[["i0OFE", args, None, "generic"]]])
    url = "https://trends.google.com/_/TrendsUi/data/batchexecute?" + urlencode({
        "rpcids": "i0OFE", "source-path": "/trending", "hl": "en-US", "rt": "c",
    })
    request = Request(
        url,
        data=urlencode({"f.req": payload}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")

    items = None
    for line in raw.splitlines():
        if not line.startswith("[["):
            continue
        try:
            frames = json.loads(line)
        except json.JSONDecodeError:
            continue
        for frame in frames:
            if isinstance(frame, list) and len(frame) >= 3 and frame[:2] == ["wrb.fr", "i0OFE"]:
                data = json.loads(frame[2])
                if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
                    raise RuntimeError("Unexpected Google Trends response format")
                items = data[1]
                break
        if items is not None:
            break
    if items is None:
        raise RuntimeError("Google Trends response contains no trending data")

    trends = []
    for item in items:
        if not isinstance(item, list) or len(item) < 11 or not isinstance(item[0], str):
            raise RuntimeError("Unexpected Google Trends trend format")
        started = item[3][0] if isinstance(item[3], list) and item[3] else None
        ended = item[4][0] if isinstance(item[4], list) and item[4] else None
        trends.append({
            "query": item[0],
            "country": item[2] or country,
            "search_volume": item[6],
            "growth_percent": item[8],
            "started_at": _utc(started),
            "ended_at": _utc(ended),
            "active": ended is None,
            "related_queries": list(item[9]) if isinstance(item[9], list) else None,
            "category_ids": list(item[10]) if isinstance(item[10], list) else None,
        })
    return trends
