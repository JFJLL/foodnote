from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import repository, schemas
from .config import get_settings
from .db import init_db
from .services.import_pipeline import ImportPipeline
from .services.system_status import get_system_status


settings = get_settings()
init_db(settings)

app = FastAPI(title="Foodnote API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.storage_root.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_root), name="storage")

ALLOWED_UPLOAD_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
}
UPLOAD_CHUNK_BYTES = 1024 * 1024


def get_pipeline() -> ImportPipeline:
    factory = getattr(app.state, "pipeline_factory", None)
    if factory:
        return factory()
    return ImportPipeline(settings)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "mimo_configured": bool(settings.mimo_api_key and settings.mimo_base_url and settings.mimo_model)}


@app.get("/api/system/status", response_model=schemas.SystemStatus)
def system_status() -> schemas.SystemStatus:
    return get_system_status(settings)


@app.post("/api/uploads", response_model=schemas.UploadOut)
async def upload_files(files: list[UploadFile] = File(...)) -> schemas.UploadOut:
    upload_dir = settings.storage_root / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise HTTPException(status_code=400, detail="仅支持图片、视频或音频素材上传。")
        target = upload_dir / f"{uuid4().hex}{suffix}"
        total_bytes = 0
        too_large = False
        with target.open("wb") as output:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_bytes:
                    too_large = True
                    break
                output.write(chunk)
        if too_large:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=413, detail="单个素材文件超过上传大小限制。")
        paths.append(str(target))
    return schemas.UploadOut(paths=paths)


@app.post("/api/import-jobs", response_model=schemas.ImportJobOut, status_code=201)
def create_import_job(
    payload: schemas.ImportJobCreate,
    background_tasks: BackgroundTasks,
) -> schemas.ImportJobOut:
    job = repository.create_import_job(payload)
    background_tasks.add_task(get_pipeline().process, job.id)
    return job


@app.get("/api/import-jobs", response_model=list[schemas.ImportJobOut])
def list_import_jobs() -> list[schemas.ImportJobOut]:
    return repository.list_import_jobs()


@app.get("/api/import-jobs/{job_id}", response_model=schemas.ImportJobOut)
def get_import_job(job_id: str) -> schemas.ImportJobOut:
    try:
        return repository.get_import_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Import job not found") from exc


@app.get("/api/recipes", response_model=list[schemas.RecipeListItem])
def list_recipes() -> list[schemas.RecipeListItem]:
    return repository.list_recipes()


@app.get("/api/recipes/random", response_model=list[schemas.RecipeListItem])
def random_recipes(count: int = 1, use_preferences: bool = True) -> list[schemas.RecipeListItem]:
    return repository.random_recipes(max(1, min(count, 10)), use_preferences=use_preferences)


@app.get("/api/preferences", response_model=schemas.HouseholdPreferencesOut)
def get_preferences() -> schemas.HouseholdPreferencesOut:
    return repository.get_preferences()


@app.patch("/api/preferences", response_model=schemas.HouseholdPreferencesOut)
def update_preferences(payload: schemas.HouseholdPreferencesUpdate) -> schemas.HouseholdPreferencesOut:
    return repository.update_preferences(payload)


@app.get("/api/recipes/{recipe_id}", response_model=schemas.RecipeDetail)
def get_recipe(recipe_id: str) -> schemas.RecipeDetail:
    try:
        return repository.get_recipe(recipe_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recipe not found") from exc


@app.patch("/api/recipes/{recipe_id}", response_model=schemas.RecipeDetail)
def update_recipe(recipe_id: str, payload: schemas.RecipeUpdate) -> schemas.RecipeDetail:
    try:
        return repository.update_recipe(recipe_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recipe not found") from exc


@app.get("/api/today-menu/items", response_model=list[schemas.TodayMenuItemOut])
def list_today_menu() -> list[schemas.TodayMenuItemOut]:
    return repository.list_today_menu()


@app.get("/api/today-menu/shopping-list", response_model=list[schemas.ShoppingListItem])
def shopping_list() -> list[schemas.ShoppingListItem]:
    return repository.build_shopping_list()


@app.get("/api/menu-orders", response_model=list[schemas.MenuOrderOut])
def list_menu_orders(limit: int = 10, query: str = "") -> list[schemas.MenuOrderOut]:
    return repository.list_menu_orders(limit, query)


@app.get("/api/cooking-stats", response_model=list[schemas.CookingStatsItem])
def cooking_stats(limit: int = 10) -> list[schemas.CookingStatsItem]:
    return repository.cooking_stats(limit)


@app.get("/api/weekly-plans", response_model=list[schemas.WeeklyPlanOut])
def list_weekly_plans(limit: int = 5) -> list[schemas.WeeklyPlanOut]:
    return repository.list_weekly_plans(limit)


@app.post("/api/weekly-plans", response_model=schemas.WeeklyPlanOut, status_code=201)
def create_weekly_plan(payload: schemas.WeeklyPlanCreate) -> schemas.WeeklyPlanOut:
    try:
        return repository.create_weekly_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/weekly-plans/{plan_id}", response_model=schemas.WeeklyPlanOut)
def get_weekly_plan(plan_id: str) -> schemas.WeeklyPlanOut:
    try:
        return repository.get_weekly_plan(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Weekly plan not found") from exc


@app.delete("/api/weekly-plans/{plan_id}", status_code=204)
def delete_weekly_plan(plan_id: str) -> None:
    try:
        repository.delete_weekly_plan(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Weekly plan not found") from exc


@app.post("/api/weekly-plans/items/{item_id}/add-to-today", response_model=schemas.TodayMenuItemOut, status_code=201)
def add_weekly_plan_item_to_today(item_id: str) -> schemas.TodayMenuItemOut:
    try:
        return repository.add_weekly_plan_item_to_today(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Weekly plan item not found") from exc


@app.get("/api/menu-orders/{order_id}", response_model=schemas.MenuOrderOut)
def get_menu_order(order_id: str) -> schemas.MenuOrderOut:
    try:
        return repository.get_menu_order(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Menu order not found") from exc


@app.post("/api/menu-orders/{order_id}/restore", response_model=list[schemas.TodayMenuItemOut])
def restore_menu_order(order_id: str) -> list[schemas.TodayMenuItemOut]:
    try:
        return repository.restore_menu_order(order_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Menu order not found") from exc


@app.post("/api/menu-orders", response_model=schemas.MenuOrderOut, status_code=201)
def create_menu_order(payload: schemas.MenuOrderCreate) -> schemas.MenuOrderOut:
    try:
        return repository.create_menu_order(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/today-menu/items", response_model=schemas.TodayMenuItemOut, status_code=201)
def add_today_menu_item(payload: schemas.TodayMenuItemCreate) -> schemas.TodayMenuItemOut:
    try:
        return repository.add_today_menu_item(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recipe not found") from exc


@app.patch("/api/today-menu/items/{item_id}", response_model=schemas.TodayMenuItemOut)
def update_today_menu_item(item_id: str, payload: schemas.TodayMenuItemUpdate) -> schemas.TodayMenuItemOut:
    try:
        return repository.update_today_menu_item(item_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Menu item not found") from exc


@app.delete("/api/today-menu/items/{item_id}", status_code=204)
def delete_today_menu_item(item_id: str) -> None:
    repository.delete_today_menu_item(item_id)


@app.delete("/api/today-menu/items", status_code=204)
def clear_today_menu() -> None:
    repository.clear_today_menu()
