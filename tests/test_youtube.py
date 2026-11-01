import io
import json
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from news_radar.youtube import YouTubeAPIError, YouTubeClient, compare_search_orders


AT = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
VIDEO_ID = "abc12345678"


def response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class YouTubeClientTests(unittest.TestCase):
    def test_search_uses_correct_filters_and_projects_videos(self):
        urls = []

        def opener(request, timeout):
            urls.append(request.full_url)
            return response({
                "items": [{
                    "id": {"videoId": VIDEO_ID},
                    "snippet": {
                        "title": "Story", "description": "Summary",
                        "channelTitle": "Publisher", "channelId": "channel",
                        "publishedAt": "2026-11-01T11:30:00Z",
                    },
                }],
                "nextPageToken": "some-page",
            })

        client = YouTubeClient("secret-key", opener=opener)
        result = client.search_videos(
            "space discovery", now=AT, hours=3,
            order="date", max_results=50, language="es", region="ES",
        )
        query = parse_qs(urlparse(urls[0]).query)
        self.assertEqual(query["part"], ["snippet"])
        self.assertEqual(query["type"], ["video"])
        self.assertEqual(query["maxResults"], ["50"])
        self.assertEqual(query["publishedAfter"], ["2026-11-01T09:00:00Z"])
        self.assertEqual(query["relevanceLanguage"], ["es"])
        self.assertEqual(query["regionCode"], ["ES"])
        self.assertEqual(result["returned_count"], 1)
        self.assertTrue(result["next_page_available"])
        self.assertEqual(result["videos"][0]["id"], VIDEO_ID)
        self.assertEqual(len(urls), 1)

    def test_probe_checks_known_video_without_playlists(self):
        calls = []

        def opener(request, timeout):
            parsed = urlparse(request.full_url)
            params = parse_qs(parsed.query)
            calls.append(parsed.path)
            if parsed.path.endswith("/videos"):
                return response({"items": [{
                    "id": VIDEO_ID,
                    "snippet": {"title": "New upload", "publishedAt": "2026-11-01T11:40:00Z"},
                    "contentDetails": {"duration": "PT4M"},
                    "statistics": {"viewCount": "13"},
                }]})
            if params["order"] == ["relevance"]:
                return response({"items": []})
            return response({"items": [{
                "id": {"videoId": VIDEO_ID},
                "snippet": {"title": "New upload", "publishedAt": "2026-11-01T11:40:00Z"},
            }]})

        client = YouTubeClient("secret-key", opener=opener)
        result = compare_search_orders(client, "discovery", expected_ids=[VIDEO_ID], hours=2, now=AT)
        self.assertEqual(result["search_calls"], 2)
        self.assertEqual(result["video_detail_calls"], 1)
        self.assertEqual(result["overlap_count"], 0)
        self.assertEqual(result["only_date_count"], 1)
        self.assertEqual(len(calls), 3)
        expected = result["expected_videos"][0]
        self.assertTrue(expected["available_via_videos_list"])
        self.assertTrue(expected["within_requested_window"])
        self.assertFalse(expected["in_relevance_first_page"])
        self.assertTrue(expected["in_date_first_page"])

    def test_empty_search_is_not_claimed_to_be_exhaustive(self):
        client = YouTubeClient("secret-key", opener=lambda request, timeout: response({"items": []}))
        result = compare_search_orders(client, "news", now=AT)
        self.assertEqual(result["relevance"]["returned_count"], 0)
        self.assertIn("do not prove", result["limitation"])

    def test_rejects_invalid_parameters_without_api_calls(self):
        client = YouTubeClient("secret-key", opener=lambda request, timeout: self.fail("Network called"))
        with self.assertRaises(ValueError):
            client.search_videos("news", max_results=51)
        with self.assertRaises(ValueError):
            client.search_videos("", max_results=50)
        with self.assertRaises(ValueError):
            client.search_videos("news", hours=0)

    def test_http_error_does_not_expose_api_key(self):
        def opener(request, timeout):
            body = response({"error": {"message": "Quota exceeded"}})
            raise HTTPError(request.full_url, 403, "Forbidden", {}, body)

        client = YouTubeClient("super-secret-key", opener=opener)
        with self.assertRaises(YouTubeAPIError) as caught:
            client.search_videos("news")
        self.assertIn("Quota exceeded", str(caught.exception))
        self.assertNotIn("super-secret-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
