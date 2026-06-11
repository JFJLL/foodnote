from __future__ import annotations

from pathlib import Path

from ..config import Settings
from .collector_adapter import CollectorConfig, extract_with_collector
from .platform_models import ExtractedAsset, PlatformExtractionError
from .yt_dlp_adapter import extract_with_ytdlp


class DouyinAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(
        self,
        *,
        source_url: str,
        manual_text: str | None = None,
        media_paths: list[str] | None = None,
        import_kind: str = "unknown",
    ) -> ExtractedAsset:
        media_paths = media_paths or []
        if manual_text:
            return self._from_manual(source_url, manual_text, media_paths, import_kind)
        if source_url.startswith("demo://douyin/video"):
            return ExtractedAsset(
                source_url=source_url,
                platform="douyin",
                kind="video",
                title="空气炸锅烤鸡翅",
                author="Foodnote Demo",
                text="",
                video_path=None,
                metadata={"demo": True, "transcript_hint": "鸡翅划刀，加生抽、蚝油、黑胡椒腌制，空气炸锅一百八十度烤十五分钟，中途翻面。"},
            )
        if source_url.startswith("demo://douyin/image"):
            return ExtractedAsset(
                source_url=source_url,
                platform="douyin",
                kind="image",
                title="凉拌黄瓜",
                author="Foodnote Demo",
                text="黄瓜拍碎，加蒜末、小米辣、生抽、醋、香油和少量糖，拌匀后冷藏十分钟。",
                image_paths=[],
                metadata={"demo": True},
            )
        return self._from_command(source_url)

    def _from_manual(
        self,
        source_url: str,
        manual_text: str,
        media_paths: list[str],
        import_kind: str,
    ) -> ExtractedAsset:
        videos = [path for path in media_paths if Path(path).suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"}]
        images = [path for path in media_paths if path not in videos]
        kind = "video" if videos or import_kind == "video" else "image"
        return ExtractedAsset(
            source_url=source_url,
            platform="douyin",
            kind=kind,
            title="手动导入菜谱",
            text=manual_text,
            image_paths=images,
            video_path=videos[0] if videos else None,
            metadata={"manual": True, "media_paths": media_paths},
        )

    def _from_command(self, source_url: str) -> ExtractedAsset:
        try:
            return extract_with_collector(
                CollectorConfig(
                    platform="douyin",
                    display_name="抖音",
                    command=self.settings.douyin_downloader_command,
                    api_base=self.settings.douyin_collector_api_base,
                    workdir=str(self.settings.collector_workdir),
                    command_env="DOUYIN_DOWNLOADER_COMMAND",
                    api_env="DOUYIN_COLLECTOR_API_BASE",
                ),
                source_url,
            )
        except PlatformExtractionError as collector_error:
            try:
                return extract_with_ytdlp(self.settings, platform="douyin", source_url=source_url)
            except PlatformExtractionError as ytdlp_error:
                raise PlatformExtractionError(f"{collector_error}；yt-dlp 后备失败：{ytdlp_error}") from ytdlp_error
