#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.32"]
# ///

"""Fetch the all-time total from Wakapi and write it into a README marker block."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE = "https://wakapi.sjfh.top/api"


def parse_json_maybe_jsonp(text: str) -> Any:
    """Return JSON object whether body is JSON or JSONP."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    # crude JSONP strip: callbackName(<json>);
    match = re.match(r"^[^(]+\((.*)\);?$", text, flags=re.S)
    if match:
        return json.loads(match.group(1))
    raise ValueError("Response is neither JSON nor JSONP")


def fetch_total(base: str, key: str, timeout: float = 30.0) -> str:
    url = f"{base.rstrip('/')}/compat/wakatime/v1/users/current/stats/all_time"
    # Wakapi wants `Basic base64(key)` — no user, no colon, unlike HTTP Basic.
    auth = base64.b64encode(key.encode()).decode()
    resp = requests.get(url, headers={"Authorization": f"Basic {auth}"}, timeout=timeout)
    if resp.status_code != 200:
        raise SystemExit(f"{url} -> HTTP {resp.status_code}: {resp.text[:300]}")
    body = parse_json_maybe_jsonp(resp.text).get("data") or {}
    # Wakapi answers a flat shape; WakaTime nests the same numbers under grand_total.
    grand = body.get("grand_total")
    total = grand.get("human_readable_total") if isinstance(grand, dict) else None
    total = total or body.get("human_readable_total")
    if not total:
        raise SystemExit(f"no human_readable_total in response: {resp.text[:300]}")
    return total


def replace_block(text: str, start: str, end: str, new_line: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start)})[\s\S]*?({re.escape(end)})",
        flags=re.M,
    )
    replacement = f"{start}\n{new_line}\n{end}"
    if not pattern.search(text):
        raise ValueError("Marker block not found in README")
    return pattern.sub(replacement, text, count=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("WAKATIME_API_BASE_URL", DEFAULT_BASE),
        help="Wakapi API root (no trailing /compat)",
    )
    parser.add_argument(
        "--readme",
        default="README.md",
        type=Path,
        help="Path to README to update",
    )
    parser.add_argument(
        "--start-marker",
        default="<!--START_SECTION:wakatime-totel-->",
        help="Start marker comment",
    )
    parser.add_argument(
        "--end-marker",
        default="<!--END_SECTION:wakatime-totel-->",
        help="End marker comment",
    )
    parser.add_argument(
        "--format",
        default="Total time spent in editors (WakaTime): {total}",
        help="Template line; use {total} as placeholder for the human-readable total",
    )
    args = parser.parse_args()

    key = os.environ.get("WAKATIME_API_KEY")
    if not key:
        raise SystemExit("WAKATIME_API_KEY is not set")

    total = fetch_total(args.api_base_url, key)
    line = args.format.format(total=total)
    readme_text = args.readme.read_text(encoding="utf-8")
    updated = replace_block(readme_text, args.start_marker, args.end_marker, line)
    args.readme.write_text(updated, encoding="utf-8")
    print(f"Updated {args.readme} with WakaTime total: {line}")


if __name__ == "__main__":
    main()
