"""Manual YouTube API searches and freshness probes.

No news ingestion, channel monitoring or automatic publishing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .youtube import YouTubeAPIError, YouTubeClient, compare_search_orders


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m news_radar",
        description="Inspect recent YouTube search coverage for a news topic.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("search", "probe"):
        command = commands.add_parser(name)
        command.add_argument("query", help="Short description of an actual news event")
        command.add_argument("--hours", type=float, default=48, help="Lookback window, default 48")
        command.add_argument("--max-results", type=int, default=50, help="Results per search (1-50)")
        command.add_argument("--language", help="Relevance language hint (e.g. es, en); not a strict filter")
        command.add_argument("--region", help="Two-letter region hint (e.g. ES, US)")
        command.add_argument("--output", type=Path, help="Optional JSON output path")
        if name == "search":
            command.add_argument("--order", choices=["relevance", "date"], default="relevance")
            command.add_argument(
                "--with-details", action="store_true",
                help="Fetch view counts/durations with one additional videos.list call",
            )
        else:
            command.add_argument(
                "--expected-id", action="append", default=[], metavar="VIDEO_ID",
                help="A known video ID to check via videos.list (repeatable, max 50)",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print("Set YOUTUBE_API_KEY in the environment first.", file=sys.stderr)
        return 2
    client = YouTubeClient(api_key)

    try:
        if args.command == "search":
            result = client.search_videos(
                args.query, hours=args.hours, order=args.order,
                max_results=args.max_results, language=args.language, region=args.region,
            )
            result["search_calls"] = 1
            result["video_detail_calls"] = 0
            if args.with_details and result["videos"]:
                details = client.videos_by_id(item["id"] for item in result["videos"])
                for item in result["videos"]:
                    item.update({
                        key: value
                        for key, value in details.get(item["id"], {}).items()
                        if key in {"view_count", "duration"}
                    })
                result["video_detail_calls"] = 1
        else:
            result = compare_search_orders(
                client, args.query, expected_ids=args.expected_id,
                hours=args.hours, max_results=args.max_results,
                language=args.language, region=args.region,
            )
    except (YouTubeAPIError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"JSON written to {args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
