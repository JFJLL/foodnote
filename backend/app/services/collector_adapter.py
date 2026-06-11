from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
from typing import Any
from urllib.parse import urlparse

import httpx

from .platform_models import ExtractedAsset, PlatformExtractionError


@dataclass(frozen=True)
class CollectorConfig:
    platform: str
    display_name: str
    command: str = ""
    api_base: str = ""
    workdir: str = ""
    command_env: str = ""
    api_env: str = ""


def extract_with_collector(config: CollectorConfig, source_url: str) -> ExtractedAsset:
    if config.command:
        payload = _run_collector_command(config, source_url)
        return normalize_collector_payload(payload, config.platform, source_url, workdir=config.workdir)
    if config.api_base:
        payload = _call_collector_api(config, source_url)
        return normalize_collector_payload(payload, config.platform, source_url, workdir=config.workdir)
    raise PlatformExtractionError(
        f"未配置 {config.display_name} 采集器。请配置 {config.command_env or 'DOWNLOADER_COMMAND'} "
        f"或 {config.api_env or 'COLLECTOR_API_BASE'}，"
        "也可以在导入面板使用手动粘贴正文/上传素材兜底。"
    )


def normalize_collector_payload(payload: dict[str, Any], platform: str, source_url: str, workdir: str | Path | None = None) -> ExtractedAsset:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    video_data = data.get("video_data") if isinstance(data.get("video_data"), dict) else {}
    video_path = _first_text(
        data,
        ["video_path", "video", "video_url", "videoFile", "下载地址"],
    ) or _first_text(video_data, ["nwm_video_url_HQ", "nwm_video_url", "wm_video_url_HQ", "play_addr", "url"])
    image_paths = _text_list(
        data.get("image_paths")
        or data.get("images")
        or data.get("image_urls")
        or data.get("图集地址")
        or video_data.get("images")
        or []
    )
    media_dir = Path(workdir) / platform if workdir else None
    image_paths = [_materialize_media_ref(path, media_dir, "image") for path in image_paths]
    if video_path:
        video_path = _materialize_media_ref(video_path, media_dir, "video")
    text = _first_text(data, ["text", "desc", "description", "content", "caption", "作品描述", "文案"]) or ""
    kind = str(data.get("kind") or ("video" if video_path else "image")).lower()
    if kind not in {"image", "video"}:
        kind = "video" if video_path else "image"
    raw_metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    metadata = dict(raw_metadata)
    metadata.setdefault("collector_payload", _without_nested_metadata(payload))
    return ExtractedAsset(
        source_url=str(data.get("source_url") or data.get("url") or source_url),
        platform=str(data.get("platform") or platform),
        kind=kind,
        title=_first_text(data, ["title", "note_title", "aweme_title", "作品标题", "标题"]),
        author=_first_text(data, ["author", "nickname", "user", "creator", "作者昵称", "作者"]),
        text=text,
        image_paths=image_paths,
        video_path=video_path,
        metadata=metadata,
    )


def _run_collector_command(config: CollectorConfig, source_url: str) -> dict[str, Any]:
    command = _split_command(config.command)
    if not command:
        raise PlatformExtractionError(f"{config.display_name} 采集命令为空")
    result = subprocess.run(
        [*command, source_url],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=config.workdir or None,
    )
    if result.returncode != 0:
        raise PlatformExtractionError(result.stderr.strip() or f"{config.display_name} 采集命令执行失败")
    return _parse_json_stdout(result.stdout, config.display_name)


def _call_collector_api(config: CollectorConfig, source_url: str) -> dict[str, Any]:
    base = config.api_base.rstrip("/")
    errors: list[str] = []
    attempts = _collector_api_attempts(config.platform, base, source_url)
    for method, endpoint, kwargs in attempts:
        try:
            with httpx.Client(timeout=180, follow_redirects=True) as client:
                response = client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            errors.append(_format_http_status_error(endpoint, exc.response))
            continue
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{endpoint}: {exc}")
            continue
        if isinstance(payload, dict):
            return payload
        errors.append(f"{endpoint}: 返回格式不是对象")
    raise PlatformExtractionError(
        f"{config.display_name} 采集 API 调用失败："
        + " | ".join(errors)
        + "。请检查采集器服务、平台登录/cookie、链接是否可公开访问；也可以改用手动粘贴正文/上传素材。"
    )


def _collector_api_attempts(platform: str, base: str, source_url: str) -> list[tuple[str, str, dict[str, Any]]]:
    attempts: list[tuple[str, str, dict[str, Any]]] = [
        ("POST", f"{base}/extract", {"json": {"platform": platform, "url": source_url}}),
    ]
    if platform == "xiaohongshu":
        attempts.append(("POST", f"{base}/xhs/detail", {"json": {"url": source_url, "download": False, "skip": False}}))
    if platform == "douyin":
        attempts.append(("GET", f"{base}/api/hybrid/video_data", {"params": {"url": source_url, "minimal": False}}))
    return attempts


def _split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        return [part.strip("\"'") for part in parts]
    return parts


def _parse_json_stdout(stdout: str, display_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PlatformExtractionError(f"{display_name} 采集命令没有输出 JSON") from exc
    if not isinstance(payload, dict):
        raise PlatformExtractionError(f"{display_name} 采集命令输出格式不是对象")
    return payload


def _format_http_status_error(endpoint: str, response: httpx.Response) -> str:
    body = response.text.strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 500:
        body = body[:500] + "..."
    if body:
        return f"{endpoint}: HTTP {response.status_code} {body}"
    return f"{endpoint}: HTTP {response.status_code}"


def _first_text(data: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _materialize_media_ref(value: str, media_dir: Path | None, media_kind: str) -> str:
    if not value.startswith(("http://", "https://")) or media_dir is None:
        return value
    return _download_media(value, media_dir, media_kind)


def _download_media(url: str, media_dir: Path, media_kind: str) -> str:
    media_dir.mkdir(parents=True, exist_ok=True)
    suffix = _suffix_for_url(url, media_kind)
    name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    target = media_dir / f"{name}{suffix}"
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            target = media_dir / f"{name}{_suffix_for_content_type(content_type, suffix)}"
            total_bytes = 0
            with target.open("wb") as output:
                for chunk in response.iter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > 250 * 1024 * 1024:
                        raise PlatformExtractionError("采集器素材超过 250MB，已停止下载。")
                    output.write(chunk)
    except httpx.HTTPError as exc:
        raise PlatformExtractionError(f"采集器素材下载失败：{url}") from exc
    return str(target)


def _suffix_for_url(url: str, media_kind: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".m4v", ".webm", ".mp3", ".m4a", ".wav", ".aac"}:
        return suffix
    return ".mp4" if media_kind == "video" else ".jpg"


def _suffix_for_content_type(content_type: str, fallback: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
    }.get(normalized, fallback)


def _without_nested_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "metadata"}
