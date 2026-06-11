from __future__ import annotations

from app.config import _load_env_file


def test_load_env_file_overrides_empty_environment_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MIMO_API_KEY=local-key\n", encoding="utf-8")
    monkeypatch.setenv("MIMO_API_KEY", "")

    _load_env_file(env_file)

    assert "local-key" == __import__("os").environ["MIMO_API_KEY"]
