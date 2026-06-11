from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
import random
from uuid import uuid4

from . import schemas
from .db import connect, from_json, now_iso, to_json


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def create_import_job(payload: schemas.ImportJobCreate) -> schemas.ImportJobOut:
    job_id = new_id("job")
    timestamp = now_iso()
    source_platform = infer_source_platform(payload.source_url, payload.source_platform)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO import_jobs (
              id, source_url, source_platform, status, import_kind, progress_message,
              manual_text, media_paths_json, created_at, updated_at
            )
            VALUES (?, ?, ?, 'queued', ?, 'Waiting to process', ?, ?, ?, ?)
            """,
            (
                job_id,
                payload.source_url,
                source_platform,
                payload.import_kind,
                payload.manual_text,
                to_json(payload.media_paths),
                timestamp,
                timestamp,
            ),
        )
    return get_import_job(job_id)


def infer_source_platform(source_url: str, requested: str = "auto") -> str:
    if requested in {"xiaohongshu", "douyin"}:
        return requested
    lowered = source_url.lower()
    if lowered.startswith("demo://douyin") or "douyin.com" in lowered or "iesdouyin.com" in lowered:
        return "douyin"
    return "xiaohongshu"


def list_import_jobs() -> list[schemas.ImportJobOut]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM import_jobs ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [_job_from_row(row) for row in rows]


def get_import_job(job_id: str) -> schemas.ImportJobOut:
    with connect() as conn:
        row = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    return _job_from_row(row)


def get_import_job_record(job_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    row["media_paths"] = from_json(row.get("media_paths_json"), [])
    return row


def retry_import_job(job_id: str) -> schemas.ImportJobOut:
    original = get_import_job_record(job_id)
    return create_import_job(
        schemas.ImportJobCreate(
            source_url=original["source_url"],
            source_platform=original["source_platform"],
            manual_text=original.get("manual_text"),
            media_paths=original.get("media_paths") or [],
            import_kind=original.get("import_kind") or "unknown",
        )
    )


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress_message: str | None = None,
    error_message: str | None = None,
    recipe_id: str | None = None,
    import_kind: str | None = None,
    raw_metadata_path: str | None = None,
) -> None:
    fields: list[str] = []
    values: list[Any] = []
    for key, value in {
        "status": status,
        "progress_message": progress_message,
        "error_message": error_message,
        "recipe_id": recipe_id,
        "import_kind": import_kind,
        "raw_metadata_path": raw_metadata_path,
    }.items():
        if value is not None:
            fields.append(f"{key} = ?")
            values.append(value)
    fields.append("updated_at = ?")
    values.append(now_iso())
    values.append(job_id)
    with connect() as conn:
        conn.execute(f"UPDATE import_jobs SET {', '.join(fields)} WHERE id = ?", values)


def list_recipes(query: str = "", platform: str = "") -> list[schemas.RecipeListItem]:
    filters: list[str] = []
    values: list[Any] = []
    normalized_query = query.strip()
    normalized_platform = platform.strip()
    if normalized_query:
        like = f"%{normalized_query}%"
        filters.append(
            """
            (
              title LIKE ? OR description LIKE ? OR tags_json LIKE ? OR
              source_title LIKE ? OR source_author LIKE ? OR source_platform LIKE ?
            )
            """
        )
        values.extend([like, like, like, like, like, like])
    if normalized_platform in {"xiaohongshu", "douyin"}:
        filters.append("source_platform = ?")
        values.append(normalized_platform)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM recipes {where_clause} ORDER BY updated_at DESC", values).fetchall()
    return [_recipe_list_from_row(row) for row in rows]


def get_recipe(recipe_id: str) -> schemas.RecipeDetail:
    with connect() as conn:
        recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if not recipe:
            raise KeyError(recipe_id)
        ingredients = conn.execute(
            "SELECT * FROM ingredients WHERE recipe_id = ? ORDER BY position ASC",
            (recipe_id,),
        ).fetchall()
        steps = conn.execute(
            "SELECT * FROM steps WHERE recipe_id = ? ORDER BY position ASC",
            (recipe_id,),
        ).fetchall()
    base = _recipe_list_from_row(recipe).model_dump()
    return schemas.RecipeDetail(
        **base,
        source_title=recipe.get("source_title"),
        source_author=recipe.get("source_author"),
        ingredients=[_ingredient_from_row(row) for row in ingredients],
        steps=[_step_from_row(row) for row in steps],
    )


def delete_recipe(recipe_id: str) -> None:
    with connect() as conn:
        result = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        if result.rowcount == 0:
            raise KeyError(recipe_id)
        conn.execute("UPDATE import_jobs SET recipe_id = NULL WHERE recipe_id = ?", (recipe_id,))


def create_recipe_from_draft(
    *,
    source_url: str,
    source_platform: str,
    source_title: str | None,
    source_author: str | None,
    raw_metadata_path: str | None,
    draft: dict[str, Any],
) -> str:
    recipe_id = new_id("recipe")
    timestamp = now_iso()
    ingredients = draft.get("ingredients") or []
    steps = draft.get("steps") or []
    tags = draft.get("tags") or []
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO recipes (
              id, title, description, cover_path, source_url, source_platform,
              source_title, source_author, confidence, tags_json, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
            """,
            (
                recipe_id,
                draft.get("title") or source_title or "未命名菜谱",
                draft.get("description") or "",
                draft.get("cover_path"),
                source_url,
                source_platform,
                source_title,
                source_author,
                float(draft.get("confidence") or 0),
                to_json(tags),
                timestamp,
                timestamp,
            ),
        )
        conn.execute(
            """
            INSERT INTO source_links (id, recipe_id, platform, url, title, author, raw_metadata_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("source"),
                recipe_id,
                source_platform,
                source_url,
                source_title,
                source_author,
                raw_metadata_path,
            ),
        )
        _replace_ingredients(conn, recipe_id, ingredients)
        _replace_steps(conn, recipe_id, steps)
    return recipe_id


def update_recipe(recipe_id: str, payload: schemas.RecipeUpdate) -> schemas.RecipeDetail:
    existing = get_recipe(recipe_id)
    update_fields: list[str] = []
    values: list[Any] = []
    for key in ["title", "description", "cover_path"]:
        value = getattr(payload, key)
        if value is not None:
            update_fields.append(f"{key} = ?")
            values.append(value)
    if payload.tags is not None:
        update_fields.append("tags_json = ?")
        values.append(to_json(payload.tags))
    if update_fields:
        update_fields.append("updated_at = ?")
        values.append(now_iso())
        values.append(recipe_id)
        with connect() as conn:
            conn.execute(f"UPDATE recipes SET {', '.join(update_fields)} WHERE id = ?", values)
    if payload.ingredients is not None:
        with connect() as conn:
            _replace_ingredients(conn, recipe_id, [item.model_dump() for item in payload.ingredients])
            conn.execute("UPDATE recipes SET updated_at = ? WHERE id = ?", (now_iso(), recipe_id))
    if payload.steps is not None:
        with connect() as conn:
            _replace_steps(conn, recipe_id, [item.model_dump() for item in payload.steps])
            conn.execute("UPDATE recipes SET updated_at = ? WHERE id = ?", (now_iso(), recipe_id))
    return get_recipe(existing.id)


def list_today_menu() -> list[schemas.TodayMenuItemOut]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.*, r.title, r.description, r.cover_path, r.source_url, r.source_platform,
                   r.confidence, r.tags_json, r.created_at AS recipe_created_at,
                   r.updated_at AS recipe_updated_at
            FROM today_menu_items t
            JOIN recipes r ON r.id = t.recipe_id
            ORDER BY t.created_at ASC
            """
        ).fetchall()
    return [_menu_item_from_row(row) for row in rows]


def add_today_menu_item(payload: schemas.TodayMenuItemCreate) -> schemas.TodayMenuItemOut:
    get_recipe(payload.recipe_id)
    item_id = new_id("menu")
    with connect() as conn:
        conn.execute(
            "INSERT INTO today_menu_items (id, recipe_id, servings, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (item_id, payload.recipe_id, payload.servings, payload.note, now_iso()),
        )
    return next(item for item in list_today_menu() if item.id == item_id)


def update_today_menu_item(item_id: str, payload: schemas.TodayMenuItemUpdate) -> schemas.TodayMenuItemOut:
    fields: list[str] = []
    values: list[Any] = []
    if payload.servings is not None:
        fields.append("servings = ?")
        values.append(payload.servings)
    if payload.note is not None:
        fields.append("note = ?")
        values.append(payload.note)
    if fields:
        values.append(item_id)
        with connect() as conn:
            result = conn.execute(f"UPDATE today_menu_items SET {', '.join(fields)} WHERE id = ?", values)
            if result.rowcount == 0:
                raise KeyError(item_id)
    for item in list_today_menu():
        if item.id == item_id:
            return item
    raise KeyError(item_id)


def delete_today_menu_item(item_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM today_menu_items WHERE id = ?", (item_id,))


def clear_today_menu() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM today_menu_items")


def create_menu_order(payload: schemas.MenuOrderCreate) -> schemas.MenuOrderOut:
    items = list_today_menu()
    if not items:
        raise ValueError("今日菜单为空，无法确认菜单。")
    order_id = new_id("order")
    timestamp = now_iso()
    title = payload.title.strip() or f"今日菜单 {timestamp[:10]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO menu_orders (id, title, note, item_count, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, title, payload.note.strip(), len(items), timestamp),
        )
        for index, item in enumerate(items):
            conn.execute(
                """
                INSERT INTO menu_order_items (
                  id, order_id, recipe_id, recipe_title, servings, note, position
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("order_item"),
                    order_id,
                    item.recipe_id,
                    item.recipe.title,
                    item.servings,
                    item.note,
                    index,
                ),
            )
        conn.execute("DELETE FROM today_menu_items")
    return get_menu_order(order_id)


def list_menu_orders(limit: int = 10, query: str = "") -> list[schemas.MenuOrderOut]:
    normalized_query = query.strip().lower()
    with connect() as conn:
        if normalized_query:
            like = f"%{normalized_query}%"
            rows = conn.execute(
                """
                SELECT DISTINCT o.*
                FROM menu_orders o
                LEFT JOIN menu_order_items i ON i.order_id = o.id
                WHERE lower(o.title) LIKE ?
                   OR lower(o.note) LIKE ?
                   OR lower(i.recipe_title) LIKE ?
                ORDER BY o.created_at DESC
                LIMIT ?
                """,
                (like, like, like, max(1, min(limit, 50))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM menu_orders ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 50)),),
            ).fetchall()
    return [get_menu_order(row["id"]) for row in rows]


def restore_menu_order(order_id: str) -> list[schemas.TodayMenuItemOut]:
    order = get_menu_order(order_id)
    with connect() as conn:
        current_rows = conn.execute("SELECT * FROM today_menu_items").fetchall()
        current_by_recipe_id = {row["recipe_id"]: row for row in current_rows}
        recipe_ids = {row["id"] for row in conn.execute("SELECT id FROM recipes").fetchall()}
        for item in order.items:
            if not item.recipe_id or item.recipe_id not in recipe_ids:
                continue
            existing = current_by_recipe_id.get(item.recipe_id)
            if existing:
                servings = min(20, int(existing.get("servings") or 1) + item.servings)
                note = _merge_notes(existing.get("note") or "", item.note)
                conn.execute(
                    "UPDATE today_menu_items SET servings = ?, note = ? WHERE id = ?",
                    (servings, note, existing["id"]),
                )
            else:
                item_id = new_id("menu")
                conn.execute(
                    "INSERT INTO today_menu_items (id, recipe_id, servings, note, created_at) VALUES (?, ?, ?, ?, ?)",
                    (item_id, item.recipe_id, item.servings, item.note, now_iso()),
                )
    return list_today_menu()


def get_menu_order(order_id: str) -> schemas.MenuOrderOut:
    with connect() as conn:
        order = conn.execute("SELECT * FROM menu_orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            raise KeyError(order_id)
        items = conn.execute(
            "SELECT * FROM menu_order_items WHERE order_id = ? ORDER BY position ASC",
            (order_id,),
        ).fetchall()
    return schemas.MenuOrderOut(
        id=order["id"],
        title=order["title"],
        note=order.get("note") or "",
        item_count=int(order.get("item_count") or 0),
        created_at=order["created_at"],
        items=[
            schemas.MenuOrderItemOut(
                id=item["id"],
                recipe_id=item.get("recipe_id"),
                recipe_title=item["recipe_title"],
                servings=int(item.get("servings") or 1),
                note=item.get("note") or "",
                position=int(item.get("position") or 0),
            )
            for item in items
        ],
    )


def get_preferences() -> schemas.HouseholdPreferencesOut:
    _ensure_preferences_row()
    with connect() as conn:
        row = conn.execute("SELECT * FROM household_preferences WHERE id = 'default'").fetchone()
    return _preferences_from_row(row)


def cooking_stats(limit: int = 10) -> list[schemas.CookingStatsItem]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
              recipe_id,
              recipe_title,
              COUNT(*) AS cooked_count,
              SUM(servings) AS servings_total,
              MAX(o.created_at) AS last_cooked_at
            FROM menu_order_items i
            JOIN menu_orders o ON o.id = i.order_id
            GROUP BY recipe_id, recipe_title
            ORDER BY cooked_count DESC, last_cooked_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 50)),),
        ).fetchall()
    return [
        schemas.CookingStatsItem(
            recipe_id=row.get("recipe_id"),
            recipe_title=row["recipe_title"],
            cooked_count=int(row.get("cooked_count") or 0),
            servings_total=int(row.get("servings_total") or 0),
            last_cooked_at=row["last_cooked_at"],
        )
        for row in rows
    ]


def list_weekly_plans(limit: int = 5) -> list[schemas.WeeklyPlanOut]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM weekly_menu_plans ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 20)),),
        ).fetchall()
    return [get_weekly_plan(row["id"]) for row in rows]


def get_weekly_plan(plan_id: str) -> schemas.WeeklyPlanOut:
    with connect() as conn:
        plan = conn.execute("SELECT * FROM weekly_menu_plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            raise KeyError(plan_id)
        item_rows = conn.execute(
            """
            SELECT
              w.*,
              r.title, r.description, r.cover_path, r.source_url, r.source_platform,
              r.confidence, r.tags_json, r.created_at AS recipe_created_at,
              r.updated_at AS recipe_updated_at
            FROM weekly_menu_plan_items w
            JOIN recipes r ON r.id = w.recipe_id
            WHERE w.plan_id = ?
            ORDER BY w.position ASC
            """,
            (plan_id,),
        ).fetchall()
    return schemas.WeeklyPlanOut(
        id=plan["id"],
        title=plan["title"],
        start_date=plan["start_date"],
        days=int(plan.get("days") or 7),
        meals_per_day=int(plan.get("meals_per_day") or 2),
        created_at=plan["created_at"],
        items=[_weekly_plan_item_from_row(row) for row in item_rows],
    )


def create_weekly_plan(payload: schemas.WeeklyPlanCreate) -> schemas.WeeklyPlanOut:
    recipes = list_recipes()
    if not recipes:
        raise ValueError("菜谱库为空，无法生成每周菜单。")
    candidates = _apply_random_preferences(recipes) or recipes
    random.shuffle(candidates)
    start = _parse_plan_start_date(payload.start_date)
    meal_labels = _meal_labels(payload.meals_per_day)
    plan_id = new_id("week")
    timestamp = now_iso()
    title = payload.title.strip() or f"每周菜单 {start.isoformat()}"
    total_slots = payload.days * payload.meals_per_day
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO weekly_menu_plans (id, title, start_date, days, meals_per_day, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (plan_id, title, start.isoformat(), payload.days, payload.meals_per_day, timestamp),
        )
        for position in range(total_slots):
            recipe = candidates[position % len(candidates)]
            day_index = position // payload.meals_per_day
            meal_label = meal_labels[position % len(meal_labels)]
            item_date = start + timedelta(days=day_index)
            conn.execute(
                """
                INSERT INTO weekly_menu_plan_items (
                  id, plan_id, recipe_id, day_index, date, meal_label, servings, note, position
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("week_item"),
                    plan_id,
                    recipe.id,
                    day_index,
                    item_date.isoformat(),
                    meal_label,
                    payload.servings,
                    "",
                    position,
                ),
            )
    return get_weekly_plan(plan_id)


def delete_weekly_plan(plan_id: str) -> None:
    with connect() as conn:
        result = conn.execute("DELETE FROM weekly_menu_plans WHERE id = ?", (plan_id,))
        if result.rowcount == 0:
            raise KeyError(plan_id)


def add_weekly_plan_item_to_today(item_id: str) -> schemas.TodayMenuItemOut:
    with connect() as conn:
        item = conn.execute("SELECT * FROM weekly_menu_plan_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        raise KeyError(item_id)
    return add_today_menu_item(
        schemas.TodayMenuItemCreate(
            recipe_id=item["recipe_id"],
            servings=int(item.get("servings") or 1),
            note=f"{item['date']} {item['meal_label']}",
        )
    )


def update_preferences(payload: schemas.HouseholdPreferencesUpdate) -> schemas.HouseholdPreferencesOut:
    _ensure_preferences_row()
    fields: list[str] = []
    values: list[Any] = []
    if payload.preferred_tags is not None:
        fields.append("preferred_tags_json = ?")
        values.append(to_json(_clean_text_list(payload.preferred_tags)))
    if payload.blocked_tags is not None:
        fields.append("blocked_tags_json = ?")
        values.append(to_json(_clean_text_list(payload.blocked_tags)))
    if payload.disliked_ingredients is not None:
        fields.append("disliked_ingredients_json = ?")
        values.append(to_json(_clean_text_list(payload.disliked_ingredients)))
    if payload.default_servings is not None:
        fields.append("default_servings = ?")
        values.append(payload.default_servings)
    if payload.avoid_recent_days is not None:
        fields.append("avoid_recent_days = ?")
        values.append(payload.avoid_recent_days)
    if fields:
        fields.append("updated_at = ?")
        values.append(now_iso())
        with connect() as conn:
            conn.execute(f"UPDATE household_preferences SET {', '.join(fields)} WHERE id = 'default'", values)
    return get_preferences()


def random_recipes(count: int = 1, *, use_preferences: bool = True) -> list[schemas.RecipeListItem]:
    recipes = list_recipes()
    if use_preferences:
        recipes = _apply_random_preferences(recipes) or recipes
    if count >= len(recipes):
        random.shuffle(recipes)
        return recipes
    return random.sample(recipes, count)


def build_shopping_list() -> list[schemas.ShoppingListItem]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.name, i.amount, i.note, r.title AS recipe_title, t.servings
            FROM today_menu_items t
            JOIN recipes r ON r.id = t.recipe_id
            JOIN ingredients i ON i.recipe_id = r.id
            ORDER BY i.name ASC, r.title ASC
            """
        ).fetchall()
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["name"].strip()
        if not key:
            continue
        item = grouped.setdefault(
            key,
            {
                "name": key,
                "amounts": [],
                "notes": [],
                "recipe_titles": [],
                "servings_total": 0,
            },
        )
        if row.get("amount"):
            item["amounts"].append(f"{row['amount']} x{row['servings']}")
        if row.get("note"):
            item["notes"].append(row["note"])
        item["recipe_titles"].append(row["recipe_title"])
        item["servings_total"] += int(row.get("servings") or 1)
    return [
        schemas.ShoppingListItem(
            name=item["name"],
            amount="；".join(dict.fromkeys(item["amounts"])),
            note="；".join(dict.fromkeys(item["notes"])),
            recipe_titles=list(dict.fromkeys(item["recipe_titles"])),
            servings_total=item["servings_total"],
        )
        for item in grouped.values()
    ]


def _merge_notes(existing: str, incoming: str) -> str:
    notes = [note.strip() for note in [existing, incoming] if note and note.strip()]
    return "；".join(dict.fromkeys(notes))


def _apply_random_preferences(recipes: list[schemas.RecipeListItem]) -> list[schemas.RecipeListItem]:
    preferences = get_preferences()
    blocked_tags = {tag.lower() for tag in preferences.blocked_tags}
    preferred_tags = {tag.lower() for tag in preferences.preferred_tags}
    disliked_ingredients = [item.lower() for item in preferences.disliked_ingredients]
    recent_recipe_ids = _recent_ordered_recipe_ids(preferences.avoid_recent_days)
    ingredients_by_recipe = _ingredients_by_recipe_id()
    candidates: list[schemas.RecipeListItem] = []
    preferred_candidates: list[schemas.RecipeListItem] = []
    for recipe in recipes:
        recipe_tags = {tag.lower() for tag in recipe.tags}
        if blocked_tags and recipe_tags.intersection(blocked_tags):
            continue
        ingredient_names = [name.lower() for name in ingredients_by_recipe.get(recipe.id, [])]
        if disliked_ingredients and any(
            disliked in ingredient_name or ingredient_name in disliked
            for ingredient_name in ingredient_names
            for disliked in disliked_ingredients
        ):
            continue
        if recipe.id in recent_recipe_ids:
            continue
        candidates.append(recipe)
        if preferred_tags and recipe_tags.intersection(preferred_tags):
            preferred_candidates.append(recipe)
    return preferred_candidates or candidates


def _recent_ordered_recipe_ids(days: int) -> set[str]:
    if days <= 0:
        return set()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT i.recipe_id
            FROM menu_order_items i
            JOIN menu_orders o ON o.id = i.order_id
            WHERE i.recipe_id IS NOT NULL AND o.created_at >= ?
            """,
            (cutoff,),
        ).fetchall()
    return {row["recipe_id"] for row in rows if row.get("recipe_id")}


def _ingredients_by_recipe_id() -> dict[str, list[str]]:
    with connect() as conn:
        rows = conn.execute("SELECT recipe_id, name FROM ingredients").fetchall()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["recipe_id"], []).append(row.get("name") or "")
    return grouped


def _clean_text_list(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    return list(dict.fromkeys(cleaned))


def _parse_plan_start_date(value: str | None) -> date:
    if value and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError("start_date 必须是 YYYY-MM-DD 格式。") from exc
    return date.today()


def _meal_labels(meals_per_day: int) -> list[str]:
    if meals_per_day == 1:
        return ["晚餐"]
    if meals_per_day == 2:
        return ["午餐", "晚餐"]
    return ["早餐", "午餐", "晚餐"]


def _ensure_preferences_row() -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO household_preferences (
              id, preferred_tags_json, blocked_tags_json, disliked_ingredients_json,
              default_servings, avoid_recent_days, updated_at
            )
            VALUES ('default', '[]', '[]', '[]', 1, 14, ?)
            """,
            (now_iso(),),
        )


def _preferences_from_row(row: dict[str, Any]) -> schemas.HouseholdPreferencesOut:
    return schemas.HouseholdPreferencesOut(
        preferred_tags=from_json(row.get("preferred_tags_json"), []),
        blocked_tags=from_json(row.get("blocked_tags_json"), []),
        disliked_ingredients=from_json(row.get("disliked_ingredients_json"), []),
        default_servings=int(row.get("default_servings") or 1),
        avoid_recent_days=int(row.get("avoid_recent_days") or 0),
        updated_at=row["updated_at"],
    )


def _replace_ingredients(conn: Any, recipe_id: str, ingredients: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
    for index, item in enumerate(ingredients):
        conn.execute(
            """
            INSERT INTO ingredients (id, recipe_id, position, name, amount, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("ing"),
                recipe_id,
                index,
                item.get("name") or "",
                item.get("amount") or "",
                item.get("note") or "",
            ),
        )


def _replace_steps(conn: Any, recipe_id: str, steps: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM steps WHERE recipe_id = ?", (recipe_id,))
    for index, item in enumerate(steps):
        conn.execute(
            """
            INSERT INTO steps (
              id, recipe_id, position, title, body, media_paths_json, transcript_excerpt, confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("step"),
                recipe_id,
                index,
                item.get("title") or "",
                item.get("body") or "",
                to_json(item.get("media_paths") or []),
                item.get("transcript_excerpt") or "",
                float(item.get("confidence") or 0),
            ),
        )


def _job_from_row(row: dict[str, Any]) -> schemas.ImportJobOut:
    return schemas.ImportJobOut(
        id=row["id"],
        source_url=row["source_url"],
        source_platform=row["source_platform"],
        status=row["status"],
        import_kind=row["import_kind"],
        progress_message=row["progress_message"],
        error_message=row.get("error_message"),
        recipe_id=row.get("recipe_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _recipe_list_from_row(row: dict[str, Any]) -> schemas.RecipeListItem:
    return schemas.RecipeListItem(
        id=row["id"],
        title=row["title"],
        description=row.get("description") or "",
        cover_path=row.get("cover_path"),
        source_url=row["source_url"],
        source_platform=row["source_platform"],
        confidence=float(row.get("confidence") or 0),
        tags=from_json(row.get("tags_json"), []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _ingredient_from_row(row: dict[str, Any]) -> schemas.IngredientOut:
    return schemas.IngredientOut(
        id=row["id"],
        position=row["position"],
        name=row["name"],
        amount=row.get("amount") or "",
        note=row.get("note") or "",
    )


def _step_from_row(row: dict[str, Any]) -> schemas.StepOut:
    return schemas.StepOut(
        id=row["id"],
        position=row["position"],
        title=row.get("title") or "",
        body=row["body"],
        media_paths=from_json(row.get("media_paths_json"), []),
        transcript_excerpt=row.get("transcript_excerpt") or "",
        confidence=float(row.get("confidence") or 0),
    )


def _menu_item_from_row(row: dict[str, Any]) -> schemas.TodayMenuItemOut:
    recipe = schemas.RecipeListItem(
        id=row["recipe_id"],
        title=row["title"],
        description=row.get("description") or "",
        cover_path=row.get("cover_path"),
        source_url=row["source_url"],
        source_platform=row["source_platform"],
        confidence=float(row.get("confidence") or 0),
        tags=from_json(row.get("tags_json"), []),
        created_at=row["recipe_created_at"],
        updated_at=row["recipe_updated_at"],
    )
    return schemas.TodayMenuItemOut(
        id=row["id"],
        recipe_id=row["recipe_id"],
        servings=int(row.get("servings") or 1),
        note=row.get("note") or "",
        created_at=row["created_at"],
        recipe=recipe,
    )


def _weekly_plan_item_from_row(row: dict[str, Any]) -> schemas.WeeklyPlanItemOut:
    recipe = schemas.RecipeListItem(
        id=row["recipe_id"],
        title=row["title"],
        description=row.get("description") or "",
        cover_path=row.get("cover_path"),
        source_url=row["source_url"],
        source_platform=row["source_platform"],
        confidence=float(row.get("confidence") or 0),
        tags=from_json(row.get("tags_json"), []),
        created_at=row["recipe_created_at"],
        updated_at=row["recipe_updated_at"],
    )
    return schemas.WeeklyPlanItemOut(
        id=row["id"],
        plan_id=row["plan_id"],
        recipe_id=row["recipe_id"],
        day_index=int(row.get("day_index") or 0),
        date=row["date"],
        meal_label=row["meal_label"],
        servings=int(row.get("servings") or 1),
        note=row.get("note") or "",
        position=int(row.get("position") or 0),
        recipe=recipe,
    )
