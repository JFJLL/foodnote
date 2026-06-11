from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Literal


JobStatus = Literal["queued", "processing", "failed", "completed"]
ImportKind = Literal["unknown", "image", "video", "manual"]
SourcePlatform = Literal["auto", "xiaohongshu", "douyin"]


class IngredientIn(BaseModel):
    name: str
    amount: str = ""
    note: str = ""


class IngredientOut(IngredientIn):
    id: str
    position: int


class StepIn(BaseModel):
    title: str = ""
    body: str
    media_paths: list[str] = Field(default_factory=list)
    transcript_excerpt: str = ""
    confidence: float = 0


class StepOut(StepIn):
    id: str
    position: int


class RecipeListItem(BaseModel):
    id: str
    title: str
    description: str = ""
    cover_path: str | None = None
    source_url: str
    source_platform: str
    confidence: float
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class RecipeDetail(RecipeListItem):
    source_title: str | None = None
    source_author: str | None = None
    ingredients: list[IngredientOut] = Field(default_factory=list)
    steps: list[StepOut] = Field(default_factory=list)


class RecipeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    cover_path: str | None = None
    tags: list[str] | None = None
    ingredients: list[IngredientIn] | None = None
    steps: list[StepIn] | None = None


class ImportJobCreate(BaseModel):
    source_url: str = Field(min_length=1)
    source_platform: SourcePlatform = "auto"
    manual_text: str | None = None
    media_paths: list[str] = Field(default_factory=list)
    import_kind: ImportKind = "unknown"

    @field_validator("source_url")
    @classmethod
    def source_url_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source_url cannot be blank")
        return stripped


class ImportJobOut(BaseModel):
    id: str
    source_url: str
    source_platform: str
    status: JobStatus
    import_kind: ImportKind
    progress_message: str
    error_message: str | None = None
    recipe_id: str | None = None
    created_at: str
    updated_at: str


class TodayMenuItemCreate(BaseModel):
    recipe_id: str
    servings: int = Field(default=1, ge=1, le=20)
    note: str = ""


class TodayMenuItemUpdate(BaseModel):
    servings: int | None = Field(default=None, ge=1, le=20)
    note: str | None = None


class TodayMenuItemOut(BaseModel):
    id: str
    recipe_id: str
    servings: int
    note: str
    created_at: str
    recipe: RecipeListItem


class UploadOut(BaseModel):
    paths: list[str]


class CollectorStatus(BaseModel):
    command_configured: bool
    api_configured: bool
    reachable: bool = False
    ready: bool


class SystemStatus(BaseModel):
    status: str = "ok"
    mimo_configured: bool
    ffmpeg_available: bool
    faster_whisper_installed: bool
    video_ready: bool
    ytdlp_configured: bool = False
    ytdlp_available: bool = False
    asr_model: str
    asr_device: str
    asr_compute_type: str
    max_upload_mb: int
    collectors: dict[str, CollectorStatus]


class ShoppingListItem(BaseModel):
    name: str
    amount: str = ""
    note: str = ""
    recipe_titles: list[str] = Field(default_factory=list)
    servings_total: int = 0


class MenuOrderCreate(BaseModel):
    title: str = ""
    note: str = ""


class MenuOrderItemOut(BaseModel):
    id: str
    recipe_id: str | None = None
    recipe_title: str
    servings: int
    note: str
    position: int


class MenuOrderOut(BaseModel):
    id: str
    title: str
    note: str
    item_count: int
    created_at: str
    items: list[MenuOrderItemOut] = Field(default_factory=list)


class CookingStatsItem(BaseModel):
    recipe_id: str | None = None
    recipe_title: str
    cooked_count: int
    servings_total: int
    last_cooked_at: str


class WeeklyPlanCreate(BaseModel):
    title: str = ""
    start_date: str | None = None
    days: int = Field(default=7, ge=1, le=14)
    meals_per_day: int = Field(default=2, ge=1, le=3)
    servings: int = Field(default=1, ge=1, le=20)


class WeeklyPlanItemOut(BaseModel):
    id: str
    plan_id: str
    recipe_id: str
    day_index: int
    date: str
    meal_label: str
    servings: int
    note: str
    position: int
    recipe: RecipeListItem


class WeeklyPlanOut(BaseModel):
    id: str
    title: str
    start_date: str
    days: int
    meals_per_day: int
    created_at: str
    items: list[WeeklyPlanItemOut] = Field(default_factory=list)


class HouseholdPreferencesUpdate(BaseModel):
    preferred_tags: list[str] | None = None
    blocked_tags: list[str] | None = None
    disliked_ingredients: list[str] | None = None
    default_servings: int | None = Field(default=None, ge=1, le=20)
    avoid_recent_days: int | None = Field(default=None, ge=0, le=365)


class HouseholdPreferencesOut(BaseModel):
    preferred_tags: list[str] = Field(default_factory=list)
    blocked_tags: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)
    default_servings: int = 1
    avoid_recent_days: int = 14
    updated_at: str
