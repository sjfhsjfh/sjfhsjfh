#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.32"]
# ///

"""Fetch WakaTime share JSON and update README marker block with grand_total.human_readable_total."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import requests


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


def fetch_total(url: str, timeout: float = 10.0) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = parse_json_maybe_jsonp(resp.text)
    try:
        return data["data"]["grand_total"]["human_readable_total"]
    except Exception as exc:  # noqa: BLE001
        raise KeyError("Missing data.grand_total.human_readable_total in response") from exc


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
        "--url",
        default="https://wakatime.com/share/@81040334-6dc6-4aad-a76c-3863c8b0c02e/d2e354b3-4097-4a04-b581-1b1ab65817a5.json",
        help="WakaTime share JSON/JSONP URL",
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

    total = fetch_total(args.url)
    line = args.format.format(total=total)
    readme_text = args.readme.read_text(encoding="utf-8")
    updated = replace_block(readme_text, args.start_marker, args.end_marker, line)
    args.readme.write_text(updated, encoding="utf-8")
    print(f"Updated {args.readme} with WakaTime total: {line}")


if __name__ == "__main__":
    main()
