from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize external social collectors for Foodnote.")
    parser.add_argument("platform", choices=["xiaohongshu", "douyin"])
    parser.add_argument("url", help="Source note/video URL")
    parser.add_argument("--command", help="External collector command. The source URL is appended.")
    parser.add_argument("--fixture", help="Read collector JSON from a local file for smoke tests.")
    parser.add_argument("--output-dir", default="storage/collectors", help="Collector working directory.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        payload = load_payload(args)
        print(json.dumps(normalize_payload(payload, args.platform, args.url), ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable stderr.
        print(str(exc), file=sys.stderr)
        return 1


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.fixture:
        payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    elif args.command:
        command = shlex.split(args.command)
        result = subprocess.run(
            [*command, args.url],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=args.output_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "external collector command failed")
        payload = json.loads(result.stdout)
    else:
        raise RuntimeError("set --command or --fixture; this bridge does not scrape platforms by itself")
    if not isinstance(payload, dict):
        raise RuntimeError("collector output must be a JSON object")
    return payload


def normalize_payload(payload: dict[str, Any], platform: str, source_url: str) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    video_path = first_text(data, ["video_path", "video", "video_url", "videoFile"])
    image_paths = text_list(data.get("image_paths") or data.get("images") or data.get("image_urls") or [])
    kind = str(data.get("kind") or ("video" if video_path else "image")).lower()
    if kind not in {"image", "video"}:
        kind = "video" if video_path else "image"
    return {
        "platform": data.get("platform") or platform,
        "kind": kind,
        "source_url": data.get("source_url") or data.get("url") or source_url,
        "title": first_text(data, ["title", "note_title", "aweme_title"]),
        "author": first_text(data, ["author", "nickname", "user", "creator"]),
        "text": first_text(data, ["text", "desc", "description", "content", "caption"]) or "",
        "image_paths": image_paths,
        "video_path": video_path,
        "metadata": payload,
    }


def first_text(data: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
