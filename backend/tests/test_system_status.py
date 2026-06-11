from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services import system_status


def test_collector_api_configured_but_unreachable_is_not_ready(monkeypatch):
    monkeypatch.setattr(system_status, "_collector_api_reachable", lambda _api_base: False)

    status = system_status._collector_status("", "http://127.0.0.1:65530")

    assert status.api_configured is True
    assert status.reachable is False
    assert status.ready is False


def test_collector_command_configured_is_ready_without_api_probe():
    status = system_status._collector_status("python fake_collector.py", "")

    assert status.command_configured is True
    assert status.api_configured is False
    assert status.ready is True


def test_system_status_reports_ytdlp_command_available(tmp_path):
    settings = Settings(
        mimo_api_key="key",
        mimo_base_url="https://mimo.example.invalid",
        mimo_model="mimo-v2.5",
        asr_model="medium",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_root=tmp_path / "storage",
        xhs_downloader_command="",
        douyin_downloader_command="",
        xhs_collector_api_base="",
        douyin_collector_api_base="",
        collector_workdir=tmp_path / "collectors",
        ytdlp_command="python fake_ytdlp.py",
    )

    status = system_status.get_system_status(settings)

    assert status.ytdlp_configured is True
    assert status.ytdlp_available is True
