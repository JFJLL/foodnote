from __future__ import annotations

from pathlib import Path
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
import sys
import threading

import pytest

from app.config import Settings
from app.services.collector_adapter import CollectorConfig, extract_with_collector, normalize_collector_payload
from app.services.douyin_adapter import DouyinAdapter
from app.services.platform_models import PlatformExtractionError
from app.services.xhs_adapter import XhsAdapter


def settings_for(tmp_path: Path, **overrides) -> Settings:
    values = {
        "mimo_api_key": "",
        "mimo_base_url": "https://mimo.example.invalid/anthropic",
        "mimo_model": "mimo-v2.5",
        "asr_model": "medium",
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "storage_root": tmp_path / "storage",
        "xhs_downloader_command": "",
        "douyin_downloader_command": "",
        "xhs_collector_api_base": "",
        "douyin_collector_api_base": "",
        "collector_workdir": tmp_path,
    }
    values.update(overrides)
    return Settings(**values)


def test_normalize_collector_payload_accepts_common_xhs_fields():
    asset = normalize_collector_payload(
        {
            "title": "葱油拌面",
            "nickname": "厨房账号",
            "desc": "熬葱油，煮面，拌匀。",
            "images": ["cover.jpg", "step.jpg"],
        },
        "xiaohongshu",
        "https://www.xiaohongshu.com/explore/fake",
    )

    assert asset.platform == "xiaohongshu"
    assert asset.kind == "image"
    assert asset.title == "葱油拌面"
    assert asset.author == "厨房账号"
    assert asset.text == "熬葱油，煮面，拌匀。"
    assert asset.image_paths == ["cover.jpg", "step.jpg"]


def test_normalize_collector_payload_metadata_can_be_serialized():
    asset = normalize_collector_payload(
        {
            "title": "清炒西兰花",
            "metadata": {"collector": "fake"},
        },
        "xiaohongshu",
        "https://www.xiaohongshu.com/explore/fake",
    )

    assert json.dumps(asset.metadata, ensure_ascii=False)


def test_normalize_collector_payload_downloads_remote_media(tmp_path):
    source_dir = tmp_path / "served"
    source_dir.mkdir()
    (source_dir / "cover.jpg").write_bytes(b"fake image")
    handler = partial(SimpleHTTPRequestHandler, directory=str(source_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/cover.jpg"
        asset = normalize_collector_payload(
            {
                "title": "葱油拌面",
                "image_urls": [url],
            },
            "xiaohongshu",
            "https://www.xiaohongshu.com/explore/fake",
            workdir=tmp_path / "collectors",
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    downloaded = Path(asset.image_paths[0])
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"fake image"
    assert downloaded.parent.name == "xiaohongshu"


def test_xhs_collector_api_falls_back_to_native_detail_endpoint(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/extract":
                self.send_response(404)
                self.end_headers()
                return
            if self.path == "/xhs/detail":
                payload = {
                    "data": {
                        "作品标题": "红烧排骨",
                        "作者昵称": "demo",
                        "作品描述": "焯水，煎香，加酱油炖。",
                        "图集地址": ["cover.jpg"],
                    }
                }
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        asset = extract_with_collector(
            CollectorConfig(
                platform="xiaohongshu",
                display_name="小红书",
                api_base=f"http://127.0.0.1:{server.server_port}",
                workdir=str(tmp_path / "collectors"),
            ),
            "https://www.xiaohongshu.com/explore/fake",
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert asset.title == "红烧排骨"
    assert asset.author == "demo"
    assert asset.text == "焯水，煎香，加酱油炖。"
    assert asset.image_paths == ["cover.jpg"]


def test_collector_api_error_includes_response_body(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(404)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"detail":"not found"}')

        def do_GET(self):
            body = '{"detail":{"message":"need cookie or login"}}'.encode("utf-8")
            self.send_response(400)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(PlatformExtractionError) as exc_info:
            extract_with_collector(
                CollectorConfig(
                    platform="douyin",
                    display_name="抖音",
                    api_base=f"http://127.0.0.1:{server.server_port}",
                    workdir=str(tmp_path / "collectors"),
                ),
                "https://www.douyin.com/video/fake",
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    message = str(exc_info.value)
    assert "HTTP 400" in message
    assert "need cookie or login" in message
    assert "手动粘贴正文" in message


def test_douyin_payload_uses_nested_video_data():
    asset = normalize_collector_payload(
        {
            "data": {
                "platform": "douyin",
                "type": "video",
                "aweme_title": "空气炸锅鸡翅",
                "desc": "腌制后空气炸锅烤熟。",
                "video_data": {"nwm_video_url_HQ": "https://example.com/video.mp4"},
            }
        },
        "douyin",
        "https://www.douyin.com/video/fake",
    )

    assert asset.kind == "video"
    assert asset.video_path == "https://example.com/video.mp4"
    assert asset.title == "空气炸锅鸡翅"


def test_xhs_adapter_uses_downloader_command(tmp_path):
    script = tmp_path / "fake_collector.py"
    script.write_text(
        "import json, sys\n"
        "print(json.dumps({'title':'红烧排骨','author':'demo','text':'焯水，煎香，加酱油炖。','url':sys.argv[1]}))\n",
        encoding="utf-8",
    )
    settings = settings_for(tmp_path, xhs_downloader_command=f'"{sys.executable}" "{script}"')

    asset = XhsAdapter(settings).extract(source_url="https://www.xiaohongshu.com/explore/fake")

    assert asset.title == "红烧排骨"
    assert asset.text == "焯水，煎香，加酱油炖。"
    assert asset.kind == "image"


def test_douyin_adapter_missing_collector_has_actionable_error(tmp_path):
    settings = settings_for(tmp_path)

    with pytest.raises(PlatformExtractionError) as exc_info:
        DouyinAdapter(settings).extract(source_url="https://www.douyin.com/video/fake")

    message = str(exc_info.value)
    assert "DOUYIN_DOWNLOADER_COMMAND" in message
    assert "DOUYIN_COLLECTOR_API_BASE" in message
    assert "手动粘贴正文" in message


def test_douyin_adapter_falls_back_to_ytdlp(tmp_path):
    script = tmp_path / "fake_ytdlp.py"
    script.write_text(
        "from pathlib import Path\n"
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        "url = args[-1]\n"
        "if '--dump-json' in args:\n"
        "    print(json.dumps({'id':'aweme_1','title':'空气炸锅鸡翅','description':'鸡翅腌制后烤熟。','uploader':'demo','webpage_url':url}))\n"
        "else:\n"
        "    template = args[args.index('-o') + 1]\n"
        "    path = Path(template.replace('%(title).80s', 'downloaded').replace('%(ext)s', 'mp4'))\n"
        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    path.write_bytes(b'fake video')\n"
        "    print(f'[download] Destination: {path}')\n",
        encoding="utf-8",
    )
    settings = settings_for(tmp_path, ytdlp_command=f'"{sys.executable}" "{script}"')

    asset = DouyinAdapter(settings).extract(source_url="https://www.douyin.com/video/fake")

    assert asset.platform == "douyin"
    assert asset.kind == "video"
    assert asset.title == "空气炸锅鸡翅"
    assert asset.author == "demo"
    assert asset.video_path
    assert Path(asset.video_path).read_bytes() == b"fake video"


def test_collector_bridge_normalizes_fixture(tmp_path):
    fixture = tmp_path / "collector.json"
    fixture.write_text(
        '{"data":{"aweme_title":"蒜蓉粉丝虾","nickname":"demo","video_path":"shrimp.mp4","caption":"蒜蓉铺虾蒸熟。"}}',
        encoding="utf-8",
    )
    script = Path(__file__).resolve().parents[2] / "scripts" / "collector_bridge.py"

    result = subprocess.run(
        [sys.executable, str(script), "douyin", "https://www.douyin.com/video/fake", "--fixture", str(fixture)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert '"platform": "douyin"' in result.stdout
    assert '"kind": "video"' in result.stdout
    assert "蒜蓉粉丝虾" in result.stdout
