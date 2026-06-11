from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..db import write_json_file
from .. import repository
from .media_processor import MediaProcessor, VideoAnalysis
from .mimo_client import MimoClient
from .douyin_adapter import DouyinAdapter
from .xhs_adapter import XhsAdapter


class ImportPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        adapter: XhsAdapter | None = None,
        adapters: dict[str, Any] | None = None,
        media_processor: MediaProcessor | None = None,
        mimo_client: MimoClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.adapters = adapters or {
            "xiaohongshu": adapter or XhsAdapter(self.settings),
            "douyin": DouyinAdapter(self.settings),
        }
        self.media_processor = media_processor or MediaProcessor(self.settings)
        self.mimo_client = mimo_client or MimoClient(self.settings)

    def process(self, job_id: str) -> None:
        repository.update_job(job_id, status="processing", progress_message="Extracting source content", error_message="")
        job = repository.get_import_job_record(job_id)
        try:
            adapter = self.adapters.get(job["source_platform"])
            if not adapter:
                raise ValueError(f"不支持的平台：{job['source_platform']}")
            asset = adapter.extract(
                source_url=job["source_url"],
                manual_text=job.get("manual_text"),
                media_paths=job.get("media_paths") or [],
                import_kind=job.get("import_kind") or "unknown",
            )
            repository.update_job(
                job_id,
                progress_message="Analyzing media",
                import_kind=asset.kind,
            )
            video_analysis: VideoAnalysis | None = None
            if asset.kind == "video":
                video_analysis = self.media_processor.analyze_video(
                    asset.video_path,
                    transcript_hint=str(asset.metadata.get("transcript_hint") or asset.text or ""),
                )
            raw_metadata_path = self._save_metadata(job_id, asset.metadata, video_analysis)
            repository.update_job(job_id, progress_message="Generating recipe draft with Mimo")
            draft = self.mimo_client.create_recipe_draft(asset=asset, video_analysis=video_analysis)
            recipe_id = repository.create_recipe_from_draft(
                source_url=asset.source_url,
                source_platform=asset.platform,
                source_title=asset.title,
                source_author=asset.author,
                raw_metadata_path=raw_metadata_path,
                draft=draft,
            )
            repository.update_job(
                job_id,
                status="completed",
                progress_message="Recipe draft ready",
                recipe_id=recipe_id,
                raw_metadata_path=raw_metadata_path,
            )
        except Exception as exc:  # noqa: BLE001 - import jobs must persist actionable failures.
            repository.update_job(
                job_id,
                status="failed",
                progress_message="Import failed",
                error_message=str(exc),
            )

    def _save_metadata(self, job_id: str, metadata: dict[str, Any], video_analysis: VideoAnalysis | None) -> str:
        payload: dict[str, Any] = {"source_metadata": metadata}
        if video_analysis:
            payload["video_analysis"] = {
                "transcript": video_analysis.transcript,
                "segments": [segment.__dict__ for segment in video_analysis.segments],
                "frame_paths": video_analysis.frame_paths,
                "speech_density": video_analysis.speech_density,
            }
        return write_json_file(Path(self.settings.storage_root) / "metadata" / f"{job_id}.json", payload)
