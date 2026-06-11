from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FOODNOTE_DISABLE_ENV_FILE", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("MIMO_API_KEY", "")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "16")
    import app.config as config
    import app.db as db
    import app.repository as repository
    import app.main as main

    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(repository)
    importlib.reload(main)
    with TestClient(main.app) as client:
        yield client, main


class FakeMimoClient:
    def create_recipe_draft(self, *, asset, video_analysis=None):
        return {
            "title": "番茄鸡蛋面",
            "description": "十分钟能做好的家常面。",
            "cover_path": asset.image_paths[0] if asset.image_paths else None,
            "tags": ["家常菜", "快手"],
            "confidence": 0.88,
            "ingredients": [
                {"name": "番茄", "amount": "1 个", "note": "切块"},
                {"name": "鸡蛋", "amount": "2 个", "note": "打散"},
            ],
            "steps": [
                {"title": "炒蛋", "body": "鸡蛋炒到凝固后盛出。", "media_paths": [], "confidence": 0.9},
                {
                    "title": "煮面",
                    "body": "番茄炒出汁后加水煮面，最后放回鸡蛋。",
                    "media_paths": [],
                    "transcript_excerpt": video_analysis.transcript if video_analysis else "",
                    "confidence": 0.86,
                },
            ],
        }


@dataclass
class FakeVideoAnalysis:
    transcript: str = "热锅下番茄，再放鸡蛋和面条。"
    segments: list = None
    frame_paths: list[str] = None
    speech_density: float = 0.7

    def __post_init__(self):
        self.segments = []
        self.frame_paths = self.frame_paths or []


class FakeMediaProcessor:
    called = False

    def analyze_video(self, video_path, transcript_hint=""):
        self.called = True
        return FakeVideoAnalysis(transcript=transcript_hint or "视频讲解文本")


def test_uploads_validate_file_type_and_size(app_client):
    client, _ = app_client

    valid = client.post("/api/uploads", files=[("files", ("cover.jpg", b"fakejpeg", "image/jpeg"))])
    assert valid.status_code == 200
    assert valid.json()["paths"][0].endswith(".jpg")

    unsupported = client.post("/api/uploads", files=[("files", ("script.exe", b"bad", "application/octet-stream"))])
    assert unsupported.status_code == 400
    assert "图片、视频或音频" in unsupported.json()["detail"]

    oversized = client.post("/api/uploads", files=[("files", ("video.mp4", b"x" * 17, "video/mp4"))])
    assert oversized.status_code == 413


def test_import_job_rejects_blank_source_url(app_client):
    client, _ = app_client

    response = client.post("/api/import-jobs", json={"source_url": "   "})

    assert response.status_code == 422


def test_system_status_reports_runtime_readiness(app_client):
    client, _ = app_client

    response = client.get("/api/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["asr_model"] == "medium"
    assert payload["asr_device"] == "cuda"
    assert payload["max_upload_mb"] >= 1
    assert "xiaohongshu" in payload["collectors"]
    assert "douyin" in payload["collectors"]


def test_health_requires_complete_mimo_configuration(app_client):
    client, _ = app_client

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["mimo_configured"] is False


def test_import_job_success_creates_recipe(app_client):
    client, main = app_client

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline
        from app.services.xhs_adapter import XhsAdapter

        return ImportPipeline(
            main.settings,
            adapter=XhsAdapter(main.settings),
            media_processor=FakeMediaProcessor(),
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    response = client.post("/api/import-jobs", json={"source_url": "demo://xhs/image"})
    assert response.status_code == 201
    job_id = response.json()["id"]

    job = client.get(f"/api/import-jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["recipe_id"]

    recipes = client.get("/api/recipes").json()
    assert len(recipes) == 1
    assert recipes[0]["title"] == "番茄鸡蛋面"

    detail = client.get(f"/api/recipes/{recipes[0]['id']}").json()
    assert [item["name"] for item in detail["ingredients"]] == ["番茄", "鸡蛋"]
    assert len(detail["steps"]) == 2


def test_recipe_list_supports_query_and_platform_filters(app_client):
    client, _ = app_client
    from app import repository

    repository.create_recipe_from_draft(
        source_url="demo://xhs/tomato",
        source_platform="xiaohongshu",
        source_title="小红书番茄鸡蛋面",
        source_author="Foodnote Demo",
        raw_metadata_path=None,
        draft={
            "title": "番茄鸡蛋面",
            "description": "十分钟家常面。",
            "tags": ["家常菜", "快手"],
            "ingredients": [],
            "steps": [],
            "confidence": 0.9,
        },
    )
    repository.create_recipe_from_draft(
        source_url="demo://douyin/shrimp",
        source_platform="douyin",
        source_title="抖音空气炸锅虾",
        source_author="Foodnote Demo",
        raw_metadata_path=None,
        draft={
            "title": "空气炸锅烤虾",
            "description": "适合周末的小菜。",
            "tags": ["空气炸锅", "海鲜"],
            "ingredients": [],
            "steps": [],
            "confidence": 0.82,
        },
    )

    assert [item["title"] for item in client.get("/api/recipes?query=番茄").json()] == ["番茄鸡蛋面"]
    assert [item["title"] for item in client.get("/api/recipes?query=海鲜").json()] == ["空气炸锅烤虾"]
    assert [item["source_platform"] for item in client.get("/api/recipes?platform=douyin").json()] == ["douyin"]
    assert client.get("/api/recipes?query=番茄&platform=douyin").json() == []


def test_import_job_records_mimo_failure(app_client):
    client, main = app_client
    if hasattr(main.app.state, "pipeline_factory"):
        delattr(main.app.state, "pipeline_factory")

    response = client.post(
        "/api/import-jobs",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/fake",
            "manual_text": "番茄炒蛋：番茄切块，鸡蛋打散，先炒蛋再炒番茄。",
        },
    )
    assert response.status_code == 201
    job = client.get(f"/api/import-jobs/{response.json()['id']}").json()
    assert job["status"] == "failed"
    assert "MIMO_API_KEY" in job["error_message"]

    class RetryMimoClient(FakeMimoClient):
        pass

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline

        return ImportPipeline(
            main.settings,
            media_processor=FakeMediaProcessor(),
            mimo_client=RetryMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    retry_response = client.post(f"/api/import-jobs/{job['id']}/retry")
    assert retry_response.status_code == 201
    retry_job = client.get(f"/api/import-jobs/{retry_response.json()['id']}").json()
    assert retry_job["id"] != job["id"]
    assert retry_job["source_url"] == job["source_url"]
    assert retry_job["source_platform"] == job["source_platform"]
    assert retry_job["import_kind"] == job["import_kind"]
    assert retry_job["status"] == "completed"
    assert retry_job["recipe_id"]
    assert client.post("/api/import-jobs/missing/retry").status_code == 404


def test_recipe_update_and_today_menu(app_client):
    client, main = app_client

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline
        from app.services.xhs_adapter import XhsAdapter

        return ImportPipeline(
            main.settings,
            adapter=XhsAdapter(main.settings),
            media_processor=FakeMediaProcessor(),
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    job = client.post("/api/import-jobs", json={"source_url": "demo://xhs/image"}).json()
    recipe_id = client.get(f"/api/import-jobs/{job['id']}").json()["recipe_id"]

    updated = client.patch(
        f"/api/recipes/{recipe_id}",
        json={
            "title": "改良番茄鸡蛋面",
            "tags": ["晚餐"],
            "ingredients": [{"name": "番茄", "amount": "2 个"}],
            "steps": [{"title": "完成", "body": "煮好后趁热吃。"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "改良番茄鸡蛋面"
    assert updated.json()["tags"] == ["晚餐"]

    menu_item = client.post("/api/today-menu/items", json={"recipe_id": recipe_id, "servings": 2}).json()
    assert menu_item["recipe"]["title"] == "改良番茄鸡蛋面"
    assert menu_item["servings"] == 2
    assert len(client.get("/api/today-menu/items").json()) == 1

    updated_menu_item = client.patch(
        f"/api/today-menu/items/{menu_item['id']}",
        json={"servings": 3, "note": "少油"},
    ).json()
    assert updated_menu_item["servings"] == 3
    assert updated_menu_item["note"] == "少油"

    shopping_list = client.get("/api/today-menu/shopping-list").json()
    assert shopping_list == [
        {
            "name": "番茄",
            "amount": "2 个 x3",
            "note": "",
            "recipe_titles": ["改良番茄鸡蛋面"],
            "servings_total": 3,
        }
    ]

    order_response = client.post("/api/menu-orders", json={"title": "周五晚餐", "note": "少油"})
    assert order_response.status_code == 201
    order = order_response.json()
    assert order["title"] == "周五晚餐"
    assert order["note"] == "少油"
    assert order["item_count"] == 1
    assert order["items"][0]["recipe_title"] == "改良番茄鸡蛋面"
    assert order["items"][0]["servings"] == 3
    assert order["items"][0]["note"] == "少油"
    assert client.get("/api/today-menu/items").json() == []

    orders = client.get("/api/menu-orders").json()
    assert orders[0]["id"] == order["id"]

    order_detail = client.get(f"/api/menu-orders/{order['id']}").json()
    assert order_detail["items"][0]["recipe_title"] == "改良番茄鸡蛋面"

    random_items = client.get("/api/recipes/random?count=1").json()
    assert len(random_items) == 1

    empty_order = client.post("/api/menu-orders", json={})
    assert empty_order.status_code == 400

    restored_menu = client.post(f"/api/menu-orders/{order['id']}/restore").json()
    assert len(restored_menu) == 1
    assert restored_menu[0]["recipe"]["title"] == "改良番茄鸡蛋面"
    assert restored_menu[0]["servings"] == 3
    assert restored_menu[0]["note"] == "少油"

    merged_menu = client.post(f"/api/menu-orders/{order['id']}/restore").json()
    assert len(merged_menu) == 1
    assert merged_menu[0]["servings"] == 6

    delete_response = client.delete(f"/api/recipes/{recipe_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/recipes/{recipe_id}").status_code == 404
    assert client.get("/api/today-menu/items").json() == []
    assert client.get(f"/api/menu-orders/{order['id']}").json()["items"][0]["recipe_title"] == "改良番茄鸡蛋面"
    assert client.post(f"/api/menu-orders/{order['id']}/restore").json() == []
    assert client.get(f"/api/import-jobs/{job['id']}").json()["recipe_id"] is None
    assert client.delete(f"/api/recipes/{recipe_id}").status_code == 404


def test_video_import_uses_media_processor(app_client):
    client, main = app_client
    media = FakeMediaProcessor()

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline
        from app.services.xhs_adapter import XhsAdapter

        return ImportPipeline(
            main.settings,
            adapter=XhsAdapter(main.settings),
            media_processor=media,
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    response = client.post("/api/import-jobs", json={"source_url": "demo://xhs/video"})
    assert response.status_code == 201
    job = client.get(f"/api/import-jobs/{response.json()['id']}").json()
    assert job["status"] == "completed"
    assert job["import_kind"] == "video"
    assert media.called is True


def test_douyin_video_import_uses_shared_pipeline(app_client):
    client, main = app_client
    media = FakeMediaProcessor()

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline

        return ImportPipeline(
            main.settings,
            media_processor=media,
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    response = client.post("/api/import-jobs", json={"source_url": "demo://douyin/video", "source_platform": "auto"})
    assert response.status_code == 201
    job = client.get(f"/api/import-jobs/{response.json()['id']}").json()
    assert job["status"] == "completed"
    assert job["source_platform"] == "douyin"
    assert job["import_kind"] == "video"
    assert media.called is True

    recipe = client.get(f"/api/recipes/{job['recipe_id']}").json()
    assert recipe["source_platform"] == "douyin"


def test_preferences_drive_random_recipe_selection(app_client):
    client, main = app_client

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline

        return ImportPipeline(
            main.settings,
            media_processor=FakeMediaProcessor(),
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    recipe_ids = []
    for source_url in ["demo://xhs/image", "demo://douyin/image"]:
        job = client.post("/api/import-jobs", json={"source_url": source_url, "source_platform": "auto"}).json()
        recipe_ids.append(client.get(f"/api/import-jobs/{job['id']}").json()["recipe_id"])

    client.patch(
        f"/api/recipes/{recipe_ids[0]}",
        json={
            "title": "番茄鸡蛋面",
            "tags": ["家常菜"],
            "ingredients": [{"name": "鸡蛋", "amount": "2 个"}],
            "steps": [{"body": "炒蛋煮面。"}],
        },
    )
    client.patch(
        f"/api/recipes/{recipe_ids[1]}",
        json={
            "title": "蒜蓉虾",
            "tags": ["海鲜"],
            "ingredients": [{"name": "虾", "amount": "300g"}],
            "steps": [{"body": "蒸熟。"}],
        },
    )

    preferences = client.patch(
        "/api/preferences",
        json={"preferred_tags": ["海鲜"], "default_servings": 2, "avoid_recent_days": 30},
    ).json()
    assert preferences["preferred_tags"] == ["海鲜"]
    assert preferences["default_servings"] == 2

    preferred_random = client.get("/api/recipes/random?count=1").json()
    assert preferred_random[0]["title"] == "蒜蓉虾"

    client.post("/api/today-menu/items", json={"recipe_id": recipe_ids[1], "servings": 1})
    client.post("/api/menu-orders", json={"title": "午餐"})

    recent_aware_random = client.get("/api/recipes/random?count=1").json()
    assert recent_aware_random[0]["title"] == "番茄鸡蛋面"

    client.patch("/api/preferences", json={"blocked_tags": ["家常菜"], "avoid_recent_days": 0})
    blocked_random = client.get("/api/recipes/random?count=5").json()
    assert all("家常菜" not in recipe["tags"] for recipe in blocked_random)


def test_menu_history_filter_and_cooking_stats(app_client):
    client, main = app_client

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline

        return ImportPipeline(
            main.settings,
            media_processor=FakeMediaProcessor(),
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    recipe_ids = []
    for source_url in ["demo://xhs/image", "demo://douyin/image"]:
        job = client.post("/api/import-jobs", json={"source_url": source_url, "source_platform": "auto"}).json()
        recipe_ids.append(client.get(f"/api/import-jobs/{job['id']}").json()["recipe_id"])

    client.patch(f"/api/recipes/{recipe_ids[0]}", json={"title": "番茄鸡蛋面"})
    client.patch(f"/api/recipes/{recipe_ids[1]}", json={"title": "凉拌黄瓜"})

    client.post("/api/today-menu/items", json={"recipe_id": recipe_ids[0], "servings": 2})
    client.post("/api/menu-orders", json={"title": "周一晚餐"})
    client.post("/api/today-menu/items", json={"recipe_id": recipe_ids[0], "servings": 1})
    client.post("/api/today-menu/items", json={"recipe_id": recipe_ids[1], "servings": 1})
    client.post("/api/menu-orders", json={"title": "清爽午餐"})

    filtered = client.get("/api/menu-orders?query=黄瓜").json()
    assert len(filtered) == 1
    assert filtered[0]["title"] == "清爽午餐"

    stats = client.get("/api/cooking-stats?limit=2").json()
    assert stats[0]["recipe_title"] == "番茄鸡蛋面"
    assert stats[0]["cooked_count"] == 2
    assert stats[0]["servings_total"] == 3
    assert stats[1]["recipe_title"] == "凉拌黄瓜"


def test_weekly_plan_generation_and_add_to_today(app_client):
    client, main = app_client

    def pipeline_factory():
        from app.services.import_pipeline import ImportPipeline

        return ImportPipeline(
            main.settings,
            media_processor=FakeMediaProcessor(),
            mimo_client=FakeMimoClient(),
        )

    main.app.state.pipeline_factory = pipeline_factory
    for source_url in ["demo://xhs/image", "demo://douyin/image"]:
        response = client.post("/api/import-jobs", json={"source_url": source_url, "source_platform": "auto"})
        assert response.status_code == 201

    plan_response = client.post(
        "/api/weekly-plans",
        json={"title": "本周吃什么", "start_date": "2026-06-15", "days": 7, "meals_per_day": 2, "servings": 2},
    )

    assert plan_response.status_code == 201
    plan = plan_response.json()
    assert plan["title"] == "本周吃什么"
    assert plan["start_date"] == "2026-06-15"
    assert len(plan["items"]) == 14
    assert plan["items"][0]["date"] == "2026-06-15"
    assert plan["items"][0]["meal_label"] == "午餐"
    assert plan["items"][1]["meal_label"] == "晚餐"
    assert plan["items"][0]["servings"] == 2

    plans = client.get("/api/weekly-plans").json()
    assert plans[0]["id"] == plan["id"]

    added = client.post(f"/api/weekly-plans/items/{plan['items'][0]['id']}/add-to-today").json()
    assert added["recipe_id"] == plan["items"][0]["recipe_id"]
    assert added["servings"] == 2
    assert "2026-06-15 午餐" == added["note"]

    delete_response = client.delete(f"/api/weekly-plans/{plan['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/weekly-plans/{plan['id']}").status_code == 404
