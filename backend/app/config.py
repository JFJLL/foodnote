from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not os.environ.get(key):
            os.environ[key] = value.strip().strip('"').strip("'")


@dataclass(frozen=True)
class Settings:
    mimo_api_key: str
    mimo_base_url: str
    mimo_model: str
    asr_model: str
    database_url: str
    storage_root: Path
    xhs_downloader_command: str
    douyin_downloader_command: str
    xhs_collector_api_base: str
    douyin_collector_api_base: str
    collector_workdir: Path
    ytdlp_command: str = ""
    ytdlp_cookies_file: str = ""
    ytdlp_cookies_from_browser: str = ""
    max_upload_bytes: int = 200 * 1024 * 1024
    asr_device: str = "cuda"
    asr_compute_type: str = "int8"

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.replace("sqlite:///", "", 1)
            path = Path(raw_path)
            if not path.is_absolute():
                return PROJECT_DIR / path
            return path
        raise ValueError("Only sqlite:/// DATABASE_URL is supported in V1")


def get_settings() -> Settings:
    if os.getenv("FOODNOTE_DISABLE_ENV_FILE") != "1":
        _load_env_file(PROJECT_DIR / ".env")
        _load_env_file(BACKEND_DIR / ".env")
    storage_root = Path(os.getenv("STORAGE_ROOT", "./storage"))
    if not storage_root.is_absolute():
        storage_root = PROJECT_DIR / storage_root
    collector_workdir = Path(os.getenv("COLLECTOR_WORKDIR", "./storage/collectors"))
    if not collector_workdir.is_absolute():
        collector_workdir = PROJECT_DIR / collector_workdir
    return Settings(
        mimo_api_key=os.getenv("MIMO_API_KEY", ""),
        mimo_base_url=os.getenv("MIMO_BASE_URL", ""),
        mimo_model=os.getenv("MIMO_MODEL", "mimo-v2.5"),
        asr_model=os.getenv("ASR_MODEL", "medium"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./foodnote.db"),
        storage_root=storage_root,
        xhs_downloader_command=os.getenv("XHS_DOWNLOADER_COMMAND", ""),
        douyin_downloader_command=os.getenv("DOUYIN_DOWNLOADER_COMMAND", ""),
        xhs_collector_api_base=os.getenv("XHS_COLLECTOR_API_BASE", ""),
        douyin_collector_api_base=os.getenv("DOUYIN_COLLECTOR_API_BASE", ""),
        collector_workdir=collector_workdir,
        ytdlp_command=os.getenv("YTDLP_COMMAND", ""),
        ytdlp_cookies_file=os.getenv("YTDLP_COOKIES_FILE", ""),
        ytdlp_cookies_from_browser=os.getenv("YTDLP_COOKIES_FROM_BROWSER", ""),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024))),
        asr_device=os.getenv("ASR_DEVICE", "cuda"),
        asr_compute_type=os.getenv("ASR_COMPUTE_TYPE", "int8"),
    )
