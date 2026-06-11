from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PlatformExtractionError(RuntimeError):
    pass


@dataclass
class ExtractedAsset:
    source_url: str
    platform: str = "xiaohongshu"
    kind: str = "image"
    title: str | None = None
    author: str | None = None
    text: str = ""
    image_paths: list[str] = field(default_factory=list)
    video_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
