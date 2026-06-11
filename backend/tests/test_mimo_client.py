from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.services.mimo_client import MimoClient, MimoError, extract_json_text, fallback_recipe_draft
from app.services.platform_models import ExtractedAsset


def test_extract_json_text_from_fenced_response():
    raw = """```json
{"title":"空气炸锅鸡翅","ingredients":[],"steps":[]}
```"""

    assert json.loads(extract_json_text(raw))["title"] == "空气炸锅鸡翅"


def test_extract_json_text_from_prose_response():
    raw = """下面是整理结果：
{"title":"空气炸锅鸡翅","ingredients":[],"steps":[]}
请确认。"""

    assert json.loads(extract_json_text(raw))["title"] == "空气炸锅鸡翅"


def test_fallback_recipe_draft_from_manual_text():
    asset = ExtractedAsset(
        source_url="https://www.douyin.com/video/fake",
        platform="douyin",
        title="手动导入菜谱",
        text="空气炸锅鸡翅：鸡翅划刀，加生抽、蚝油、黑胡椒腌制。空气炸锅180度烤15分钟。",
    )

    draft = fallback_recipe_draft(asset, None)

    assert draft["title"] == "空气炸锅鸡翅"
    assert draft["ingredients"]
    assert draft["steps"]
    assert all(step["body"] != "手动导入菜谱" for step in draft["steps"])


def test_mimo_client_requires_base_url():
    client = MimoClient(
        Settings(
            mimo_api_key="local-key",
            mimo_base_url="",
            mimo_model="mimo-v2.5",
            asr_model="medium",
            database_url="sqlite:///./test.db",
            storage_root=Path("storage"),
            xhs_downloader_command="",
            douyin_downloader_command="",
            xhs_collector_api_base="",
            douyin_collector_api_base="",
            collector_workdir=Path("storage/collectors"),
        )
    )
    asset = ExtractedAsset(
        source_url="https://example.com/note",
        platform="xiaohongshu",
        kind="image",
        title="番茄鸡蛋面",
        text="番茄鸡蛋面：番茄炒出汁后加面条。",
    )

    with pytest.raises(MimoError, match="MIMO_BASE_URL"):
        client.create_recipe_draft(asset=asset)
