from __future__ import annotations

from pathlib import Path
import base64
import json
import mimetypes
from typing import Any

import httpx

from ..config import Settings
from .media_processor import VideoAnalysis
from .platform_models import ExtractedAsset


class MimoError(RuntimeError):
    pass


class MimoClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_recipe_draft(
        self,
        *,
        asset: ExtractedAsset,
        video_analysis: VideoAnalysis | None = None,
    ) -> dict[str, Any]:
        if asset.metadata.get("demo"):
            return demo_recipe_draft(asset, video_analysis)
        if not self.settings.mimo_api_key:
            raise MimoError("MIMO_API_KEY 为空，无法生成菜谱草稿。请在本地 .env 中填入轮换后的 key。")
        if not self.settings.mimo_base_url:
            raise MimoError("MIMO_BASE_URL 为空，无法生成菜谱草稿。请在本地 .env 中填入模型服务地址。")

        prompt = self._build_prompt(asset, video_analysis)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for media_path in [*asset.image_paths, *(video_analysis.frame_paths if video_analysis else [])][:12]:
            image_block = self._image_block(media_path)
            if image_block:
                content.append(image_block)

        endpoint = self.settings.mimo_base_url.rstrip("/")
        if not endpoint.endswith("/v1/messages"):
            endpoint = f"{endpoint}/v1/messages"
        payload = {
            "model": self.settings.mimo_model,
            "max_tokens": 2500,
            "messages": [{"role": "user", "content": content}],
        }
        headers = {
            "x-api-key": self.settings.mimo_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MimoError(f"Mimo 请求失败：{exc}") from exc

        try:
            return self._parse_response(response.json())
        except MimoError:
            return fallback_recipe_draft(asset, video_analysis)

    def _build_prompt(self, asset: ExtractedAsset, video_analysis: VideoAnalysis | None) -> str:
        transcript = video_analysis.transcript if video_analysis else ""
        speech_density = video_analysis.speech_density if video_analysis else None
        return f"""
你是一个中文家庭菜谱整理助手。请把短视频/图文平台上的美食内容整理为结构化菜谱 JSON，只返回 JSON，不要 Markdown。

要求：
- 如果内容不是做菜，返回仍然是 JSON，但 title 写为“待确认菜谱”，confidence 低于 0.35。
- 食材和步骤允许根据图文/关键帧合理推断，但不要编造精确克数。
- 视频有语音时，优先按 ASR 时间顺序组织步骤；语音少时，根据关键帧做视觉推断，并降低 confidence。
- 每个步骤 body 用适合复做的中文短句。
- 输出字段：title, description, cover_path, tags, confidence, ingredients, steps。
- ingredients: name, amount, note。
- steps: title, body, media_paths, transcript_excerpt, confidence。

来源标题：{asset.title or ""}
作者：{asset.author or ""}
来源平台：{asset.platform}
来源类型：{asset.kind}
来源正文：
{asset.text}

视频 ASR：
{transcript}

语音密度：{speech_density}
可用图片/关键帧路径：
{json.dumps([*asset.image_paths, *(video_analysis.frame_paths if video_analysis else [])], ensure_ascii=False)}
""".strip()

    def _image_block(self, media_path: str) -> dict[str, Any] | None:
        path = Path(media_path)
        if not path.exists() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            return None
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        }

    def _parse_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        text_parts: list[str] = []
        for block in payload.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        raw_text = "\n".join(text_parts).strip()
        raw_text = extract_json_text(raw_text)
        try:
            draft = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise MimoError("Mimo 没有返回可解析的 JSON 菜谱。") from exc
        return normalize_recipe_draft(draft)


def extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    if text.startswith("{"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def normalize_recipe_draft(draft: dict[str, Any]) -> dict[str, Any]:
    ingredients = [
        {
            "name": str(item.get("name") or "").strip(),
            "amount": str(item.get("amount") or "").strip(),
            "note": str(item.get("note") or "").strip(),
        }
        for item in draft.get("ingredients", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    steps = [
        {
            "title": str(item.get("title") or "").strip(),
            "body": str(item.get("body") or "").strip(),
            "media_paths": item.get("media_paths") if isinstance(item.get("media_paths"), list) else [],
            "transcript_excerpt": str(item.get("transcript_excerpt") or "").strip(),
            "confidence": float(item.get("confidence") or draft.get("confidence") or 0),
        }
        for item in draft.get("steps", [])
        if isinstance(item, dict) and str(item.get("body") or "").strip()
    ]
    return {
        "title": str(draft.get("title") or "未命名菜谱").strip(),
        "description": str(draft.get("description") or "").strip(),
        "cover_path": draft.get("cover_path"),
        "tags": [str(tag).strip() for tag in draft.get("tags", []) if str(tag).strip()],
        "confidence": float(draft.get("confidence") or 0),
        "ingredients": ingredients,
        "steps": steps,
    }


def fallback_recipe_draft(asset: ExtractedAsset, video_analysis: VideoAnalysis | None) -> dict[str, Any]:
    generic_titles = {"手动导入菜谱", "待编辑菜谱", "未命名菜谱"}
    source_text = "\n".join(
        part
        for part in [
            asset.title if asset.title and asset.title not in generic_titles else "",
            asset.text or "",
            video_analysis.transcript if video_analysis else "",
        ]
        if part.strip()
    )
    title_source = asset.text or (video_analysis.transcript if video_analysis else "") or asset.title or ""
    title = asset.title or "待编辑菜谱"
    if "：" in title_source:
        title = title_source.split("：", 1)[0].strip() or title
    elif ":" in title_source:
        title = title_source.split(":", 1)[0].strip() or title
    fragments = [
        fragment.strip(" ，,。；;")
        for fragment in source_text.replace("\n", "。").replace("；", "。").split("。")
        if fragment.strip(" ，,。；;")
    ]
    ingredients: list[dict[str, str]] = []
    if len(fragments) > 1:
        first_step = fragments[1] if fragments[0] == title else fragments[0]
        for token in ["鸡翅", "生抽", "蚝油", "黑胡椒", "蒜末", "白芝麻", "番茄", "鸡蛋", "面条", "虾", "黄油"]:
            if token in first_step or token in source_text:
                ingredients.append({"name": token, "amount": "适量", "note": ""})
    steps = [
        {
            "title": f"步骤 {index + 1}",
            "body": fragment,
            "media_paths": [],
            "transcript_excerpt": "",
            "confidence": 0.42,
        }
        for index, fragment in enumerate(fragments[:8])
        if fragment != title
    ]
    if not steps and source_text:
        steps = [{"title": "整理原文", "body": source_text, "media_paths": [], "transcript_excerpt": "", "confidence": 0.35}]
    return normalize_recipe_draft(
        {
            "title": title,
            "description": "Mimo 返回格式不稳定时生成的可编辑草稿，请人工确认。",
            "cover_path": asset.image_paths[0] if asset.image_paths else None,
            "tags": ["待确认", "手动兜底"],
            "confidence": 0.42,
            "ingredients": ingredients,
            "steps": steps,
        }
    )


def demo_recipe_draft(asset: ExtractedAsset, video_analysis: VideoAnalysis | None) -> dict[str, Any]:
    if asset.kind == "video":
        transcript = video_analysis.transcript if video_analysis else ""
        if "鸡翅" in (asset.title or ""):
            return normalize_recipe_draft(
                {
                    "title": asset.title or "空气炸锅烤鸡翅",
                    "description": "空气炸锅版家常鸡翅，先腌制再烤，中途翻面让表面更香。",
                    "cover_path": None,
                    "tags": ["抖音视频", "空气炸锅", "家常菜"],
                    "confidence": 0.74,
                    "ingredients": [
                        {"name": "鸡翅", "amount": "适量", "note": "划刀方便入味"},
                        {"name": "生抽", "amount": "适量", "note": "腌制用"},
                        {"name": "蚝油", "amount": "适量", "note": ""},
                        {"name": "黑胡椒", "amount": "少量", "note": ""},
                    ],
                    "steps": [
                        {"title": "处理鸡翅", "body": "鸡翅洗净后划刀，方便腌料进入。", "transcript_excerpt": transcript, "confidence": 0.76},
                        {"title": "腌制", "body": "加入生抽、蚝油和黑胡椒拌匀，静置入味。", "transcript_excerpt": transcript, "confidence": 0.74},
                        {"title": "空气炸锅烤制", "body": "一百八十度烤十五分钟左右，中途翻面，表面上色后取出。", "transcript_excerpt": transcript, "confidence": 0.72},
                    ],
                }
            )
        return normalize_recipe_draft(
            {
                "title": asset.title or "蒜香黄油虾",
                "description": "适合晚餐的快手海鲜菜，黄油和蒜香是主味。",
                "cover_path": None,
                "tags": ["视频解析", "快手菜", "海鲜"],
                "confidence": 0.72,
                "ingredients": [
                    {"name": "虾", "amount": "适量", "note": "开背或去虾线"},
                    {"name": "黄油", "amount": "一小块", "note": ""},
                    {"name": "蒜末", "amount": "适量", "note": "切细"},
                ],
                "steps": [
                    {"title": "爆香", "body": "热锅融化黄油，放入蒜末炒出香味。", "transcript_excerpt": transcript, "confidence": 0.74},
                    {"title": "煎虾", "body": "放入虾，两面煎到变色并裹上蒜香黄油。", "transcript_excerpt": transcript, "confidence": 0.74},
                    {"title": "调味", "body": "撒黑胡椒和欧芹，趁热出锅。", "transcript_excerpt": transcript, "confidence": 0.68},
                ],
            }
        )
    return normalize_recipe_draft(
        {
            "title": asset.title or "番茄鸡蛋面",
            "description": "番茄出汁后煮面，最后回锅鸡蛋，适合不知道吃什么的时候。",
            "cover_path": asset.image_paths[0] if asset.image_paths else None,
            "tags": ["图文解析", "家常菜", "快手"],
            "confidence": 0.82,
            "ingredients": [
                {"name": "番茄", "amount": "1 个", "note": "切块"},
                {"name": "鸡蛋", "amount": "2 个", "note": "打散"},
                {"name": "面条", "amount": "1 份", "note": ""},
            ],
            "steps": [
                {"title": "处理食材", "body": "番茄切块，鸡蛋打散备用。", "confidence": 0.84},
                {"title": "炒出番茄汁", "body": "先炒鸡蛋盛出，再下番茄炒到出汁。", "confidence": 0.82},
                {"title": "煮面完成", "body": "加水煮开后下面条，最后放回鸡蛋并撒葱花。", "confidence": 0.8},
            ],
        }
    )
