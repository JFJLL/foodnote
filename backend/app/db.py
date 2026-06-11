from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Iterable, Iterator

from .config import Settings, get_settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def dict_factory(cursor: sqlite3.Cursor, row: Iterable[Any]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    with connect(settings) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS import_jobs (
              id TEXT PRIMARY KEY,
              source_url TEXT NOT NULL,
              source_platform TEXT NOT NULL DEFAULT 'xiaohongshu',
              status TEXT NOT NULL,
              import_kind TEXT NOT NULL DEFAULT 'unknown',
              progress_message TEXT NOT NULL DEFAULT '',
              error_message TEXT,
              recipe_id TEXT,
              manual_text TEXT,
              media_paths_json TEXT NOT NULL DEFAULT '[]',
              raw_metadata_path TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recipes (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              cover_path TEXT,
              source_url TEXT NOT NULL,
              source_platform TEXT NOT NULL,
              source_title TEXT,
              source_author TEXT,
              confidence REAL NOT NULL DEFAULT 0,
              tags_json TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'draft',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ingredients (
              id TEXT PRIMARY KEY,
              recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              name TEXT NOT NULL,
              amount TEXT NOT NULL DEFAULT '',
              note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS steps (
              id TEXT PRIMARY KEY,
              recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              media_paths_json TEXT NOT NULL DEFAULT '[]',
              transcript_excerpt TEXT NOT NULL DEFAULT '',
              confidence REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS source_links (
              id TEXT PRIMARY KEY,
              recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
              platform TEXT NOT NULL,
              url TEXT NOT NULL,
              title TEXT,
              author TEXT,
              raw_metadata_path TEXT
            );

            CREATE TABLE IF NOT EXISTS today_menu_items (
              id TEXT PRIMARY KEY,
              recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
              servings INTEGER NOT NULL DEFAULT 1,
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS menu_orders (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL DEFAULT '',
              note TEXT NOT NULL DEFAULT '',
              item_count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS menu_order_items (
              id TEXT PRIMARY KEY,
              order_id TEXT NOT NULL REFERENCES menu_orders(id) ON DELETE CASCADE,
              recipe_id TEXT,
              recipe_title TEXT NOT NULL,
              servings INTEGER NOT NULL DEFAULT 1,
              note TEXT NOT NULL DEFAULT '',
              position INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS household_preferences (
              id TEXT PRIMARY KEY,
              preferred_tags_json TEXT NOT NULL DEFAULT '[]',
              blocked_tags_json TEXT NOT NULL DEFAULT '[]',
              disliked_ingredients_json TEXT NOT NULL DEFAULT '[]',
              default_servings INTEGER NOT NULL DEFAULT 1,
              avoid_recent_days INTEGER NOT NULL DEFAULT 14,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS weekly_menu_plans (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL DEFAULT '',
              start_date TEXT NOT NULL,
              days INTEGER NOT NULL DEFAULT 7,
              meals_per_day INTEGER NOT NULL DEFAULT 2,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS weekly_menu_plan_items (
              id TEXT PRIMARY KEY,
              plan_id TEXT NOT NULL REFERENCES weekly_menu_plans(id) ON DELETE CASCADE,
              recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
              day_index INTEGER NOT NULL,
              date TEXT NOT NULL,
              meal_label TEXT NOT NULL,
              servings INTEGER NOT NULL DEFAULT 1,
              note TEXT NOT NULL DEFAULT '',
              position INTEGER NOT NULL
            );
            """
        )
        _ensure_column(conn, "today_menu_items", "servings", "INTEGER NOT NULL DEFAULT 1")
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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def write_json_file(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(value), encoding="utf-8")
    return str(path)
