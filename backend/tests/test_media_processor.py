from __future__ import annotations

from app.config import Settings
from app.services.media_processor import MediaProcessor


def test_whisper_model_falls_back_to_cpu_when_cuda_is_unavailable(tmp_path):
    calls: list[tuple[str, str]] = []

    class FakeWhisperModel:
        def __init__(self, _model_name, *, device, compute_type):
            calls.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("CUDA unavailable")

    settings = Settings(
        mimo_api_key="",
        mimo_base_url="https://mimo.example.invalid/anthropic",
        mimo_model="mimo-v2.5",
        asr_model="medium",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_root=tmp_path / "storage",
        xhs_downloader_command="",
        douyin_downloader_command="",
        xhs_collector_api_base="",
        douyin_collector_api_base="",
        collector_workdir=tmp_path,
        asr_device="cuda",
        asr_compute_type="int8",
    )

    MediaProcessor(settings)._create_whisper_model(FakeWhisperModel)

    assert calls == [("cuda", "int8"), ("cpu", "int8")]
