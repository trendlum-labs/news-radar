"""Google Trends Trending Now RSS feed."""

from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


NS = {"ht": "https://trends.google.com/trending/rss"}


def get_trends(country: str = "ES") -> list[dict]:
    """Return current Google search trends and their related news for a country."""
    country = country.upper()
    if len(country) != 2 or not country.isalpha():
        raise ValueError("country must be a two-letter country code")

    url = "https://trends.google.com/trending/rss?" + urlencode({"geo": country})
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        root = ET.parse(response).getroot()

    trends = []
    for item in root.findall("./channel/item"):
        published = item.findtext("pubDate")
        news = [
            {
                "title": article.findtext("ht:news_item_title", namespaces=NS),
                "url": article.findtext("ht:news_item_url", namespaces=NS),
                "source": article.findtext("ht:news_item_source", namespaces=NS),
            }
            for article in item.findall("ht:news_item", NS)
        ]
        trends.append({
            "country": country,
            "query": item.findtext("title"),
            "approx_traffic": item.findtext("ht:approx_traffic", namespaces=NS),
            "published_at": (
                parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
                if published else None
            ),
            "news": news,
        })
    return trends
