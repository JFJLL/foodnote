from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shlex
import shutil
import subprocess
import hashlib
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import PROJECT_DIR, Settings
from .platform_models import ExtractedAsset, PlatformExtractionError


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def ytdlp_command_parts(settings: Settings) -> list[str]:
    if settings.ytdlp_command.strip():
        return _split_command(settings.ytdlp_command)
    local_exe = PROJECT_DIR / "tools" / "external" / "yt-dlp" / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
    if local_exe.exists():
        return [str(local_exe)]
    discovered = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if discovered:
        return [discovered]
    return []


def ytdlp_available(settings: Settings) -> bool:
    return bool(ytdlp_command_parts(settings))


def extract_with_ytdlp(settings: Settings, *, platform: str, source_url: str) -> ExtractedAsset:
    command = ytdlp_command_parts(settings)
    if not command:
        raise PlatformExtractionError(
            "yt-dlp 后备采集器未安装。请运行 scripts/install_ytdlp.ps1 或配置 YTDLP_COMMAND；"
            "也可以继续使用手动粘贴正文/上传素材兜底。"
        )

    workdir = Path(settings.collector_workdir) / "yt-dlp" / platform / hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    workdir.mkdir(parents=True, exist_ok=True)
    info = _probe_metadata(command, settings, source_url, workdir)
    video_path = _download_video(command, settings, source_url, workdir)
    thumbnail = _materialize_thumbnail(info.get("thumbnail"), workdir)
    text = _first_text(info, ["description", "fulltitle", "title"]) or ""
    return ExtractedAsset(
        source_url=str(info.get("webpage_url") or source_url),
        platform=platform,
        kind="video",
        title=_first_text(info, ["title", "fulltitle"]),
        author=_first_text(info, ["uploader", "channel", "creator", "uploader_id"]),
        text=text,
        image_paths=[thumbnail] if thumbnail else [],
        video_path=video_path,
        metadata={
            "yt_dlp": {
                "id": info.get("id"),
                "extractor": info.get("extractor"),
                "duration": info.get("duration"),
                "webpage_url": info.get("webpage_url"),
            }
        },
    )


def _probe_metadata(command: list[str], settings: Settings, source_url: str, workdir: Path) -> dict[str, Any]:
    args = [
        *command,
        "--dump-json",
        "--no-playlist",
        "--no-check-certificates",
        "--user-agent",
        USER_AGENT,
        "--add-header",
        "Accept-Language:zh-CN,zh;q=0.9,en;q=0.8",
        source_url,
    ]
    args = _with_cookie_args(args, settings)
    result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=180, cwd=workdir)
    if result.returncode != 0:
        raise PlatformExtractionError(_trim_error(result.stderr) or "yt-dlp 元数据解析失败")
    return _parse_json_stdout(result.stdout)


def _download_video(command: list[str], settings: Settings, source_url: str, workdir: Path) -> str:
    output_template = str(workdir / "%(title).80s.%(ext)s")
    args = [
        *command,
        "-f",
        "bv*+ba/best",
        "-o",
        output_template,
        "--newline",
        "--no-playlist",
        "--encoding",
        "utf-8",
        "--merge-output-format",
        "mp4",
        source_url,
    ]
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg:
        args.insert(-1, ffmpeg)
        args.insert(-2, "--ffmpeg-location")
    args = _with_cookie_args(args, settings)
    result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=900, cwd=workdir)
    if result.returncode != 0:
        raise PlatformExtractionError(_trim_error(result.stderr) or "yt-dlp 视频下载失败")
    downloaded = _downloaded_path_from_output(result.stdout, workdir) or _newest_media_file(workdir)
    if not downloaded:
        raise PlatformExtractionError("yt-dlp 下载完成但没有找到本地视频文件。")
    return str(downloaded)


def _with_cookie_args(args: list[str], settings: Settings) -> list[str]:
    if settings.ytdlp_cookies_file and Path(settings.ytdlp_cookies_file).exists():
        return [*args[:-1], "--cookies", settings.ytdlp_cookies_file, args[-1]]
    if settings.ytdlp_cookies_from_browser.strip():
        return [*args[:-1], "--cookies-from-browser", settings.ytdlp_cookies_from_browser.strip(), args[-1]]
    return args


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        candidates = [line.strip() for line in text.splitlines() if line.strip().startswith("{")]
        if not candidates:
            raise PlatformExtractionError("yt-dlp 没有输出 JSON 元数据")
        payload = json.loads(candidates[-1])
    if not isinstance(payload, dict):
        raise PlatformExtractionError("yt-dlp JSON 元数据不是对象")
    return payload


def _downloaded_path_from_output(stdout: str, workdir: Path) -> Path | None:
    patterns = [
        r"\[download\] Destination: (.+)",
        r"\[download\] (.+) has already been downloaded",
        r"\[Merger\] Merging formats into \"(.+)\"",
    ]
    for line in stdout.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            raw = match.group(1).strip().strip('"')
            path = Path(raw)
            if not path.is_absolute():
                path = workdir / path
            if path.exists():
                return path
    return None


def _newest_media_file(workdir: Path) -> Path | None:
    candidates = [path for path in workdir.glob("*") if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _materialize_thumbnail(value: Any, workdir: Path) -> str | None:
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        return None
    suffix = Path(urlparse(value).path).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        suffix = ".jpg"
    target = workdir / f"thumbnail{suffix}"
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    try:
        with httpx.stream("GET", value, follow_redirects=True, timeout=60, headers={"user-agent": USER_AGENT}) as response:
            response.raise_for_status()
            total = 0
            with target.open("wb") as output:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 20 * 1024 * 1024:
                        return None
                    output.write(chunk)
    except httpx.HTTPError:
        return None
    return str(target)


def _first_text(data: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        return [part.strip("\"'") for part in parts]
    return parts


def _trim_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if not lines:
        return ""
    message = lines[-1]
    return message if len(message) <= 600 else message[:600] + "..."
