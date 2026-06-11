from __future__ import annotations

from pathlib import Path

from ..config import Settings
from .collector_adapter import CollectorConfig, extract_with_collector
from .platform_models import ExtractedAsset, PlatformExtractionError
from .yt_dlp_adapter import extract_with_ytdlp


class XhsAdapter:
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
        if source_url.startswith("demo://xhs/image"):
            return ExtractedAsset(
                source_url=source_url,
                kind="image",
                title="番茄鸡蛋面",
                author="Foodnote Demo",
                text="番茄切块，鸡蛋打散。先炒鸡蛋盛出，再炒番茄出汁，加水煮面，最后放鸡蛋和葱花。",
                image_paths=[],
                metadata={"demo": True},
            )
        if source_url.startswith("demo://xhs/video"):
            return ExtractedAsset(
                source_url=source_url,
                kind="video",
                title="蒜香黄油虾",
                author="Foodnote Demo",
                text="",
                video_path=None,
                metadata={"demo": True, "transcript_hint": "热锅下黄油和蒜末，放入虾煎到变色，撒黑胡椒和欧芹。"},
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
                    platform="xiaohongshu",
                    display_name="小红书",
                    command=self.settings.xhs_downloader_command,
                    api_base=self.settings.xhs_collector_api_base,
                    workdir=str(self.settings.collector_workdir),
                    command_env="XHS_DOWNLOADER_COMMAND",
                    api_env="XHS_COLLECTOR_API_BASE",
                ),
                source_url,
            )
        except PlatformExtractionError as collector_error:
            try:
                return extract_with_ytdlp(self.settings, platform="xiaohongshu", source_url=source_url)
            except PlatformExtractionError as ytdlp_error:
                raise PlatformExtractionError(f"{collector_error}；yt-dlp 后备失败：{ytdlp_error}") from ytdlp_error
