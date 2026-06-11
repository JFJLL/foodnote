from __future__ import annotations

from importlib.util import find_spec
import shutil

import httpx

from .. import schemas
from ..config import Settings
from .yt_dlp_adapter import ytdlp_available


def get_system_status(settings: Settings) -> schemas.SystemStatus:
    ffmpeg_available = shutil.which("ffmpeg") is not None
    faster_whisper_installed = find_spec("faster_whisper") is not None
    ytdlp_ready = ytdlp_available(settings)
    collectors = {
        "xiaohongshu": _collector_status(settings.xhs_downloader_command, settings.xhs_collector_api_base),
        "douyin": _collector_status(settings.douyin_downloader_command, settings.douyin_collector_api_base),
    }
    return schemas.SystemStatus(
        mimo_configured=bool(settings.mimo_api_key and settings.mimo_base_url and settings.mimo_model),
        ffmpeg_available=ffmpeg_available,
        faster_whisper_installed=faster_whisper_installed,
        video_ready=ffmpeg_available and faster_whisper_installed,
        ytdlp_configured=bool(settings.ytdlp_command.strip()),
        ytdlp_available=ytdlp_ready,
        asr_model=settings.asr_model,
        asr_device=settings.asr_device,
        asr_compute_type=settings.asr_compute_type,
        max_upload_mb=max(1, settings.max_upload_bytes // (1024 * 1024)),
        collectors=collectors,
    )


def _collector_status(command: str, api_base: str) -> schemas.CollectorStatus:
    command_configured = bool(command.strip())
    api_configured = bool(api_base.strip())
    reachable = _collector_api_reachable(api_base) if api_configured else False
    return schemas.CollectorStatus(
        command_configured=command_configured,
        api_configured=api_configured,
        reachable=reachable,
        ready=command_configured or reachable,
    )


def _collector_api_reachable(api_base: str) -> bool:
    try:
        response = httpx.get(api_base.rstrip("/"), follow_redirects=True, timeout=1)
        return response.status_code < 500
    except httpx.HTTPError:
        return False
