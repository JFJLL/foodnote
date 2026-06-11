# Foodnote

Foodnote is a local-first food recipe parser and home menu tool. Paste a Xiaohongshu or Douyin food link, let the backend extract text/media, use local ASR for videos, ask Mimo to draft a recipe, then edit and save it into a personal dish library.

V1 focuses on a local Web MVP:

- Xiaohongshu and Douyin import jobs
- Image note and video note parsing pipeline
- Local `faster-whisper` ASR strategy for video
- Mimo-powered recipe extraction
- Editable recipe library
- Today's menu list with servings, notes, random picks, and shopping list
- Weekly menu planning from the recipe library and taste preferences
- Manual fallback when platform scraping fails
- WeChat Mini Program shell that reuses the backend recipe/menu APIs

## Stack

- Backend: FastAPI, SQLite, `ffmpeg`, optional `faster-whisper`
- Frontend: React, Vite, TailwindCSS, lucide icons
- Storage: SQLite for structured data, `storage/` for media/transcripts/frames

## Setup

Backend:

```bash
cd backend
uv venv
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

If the backend is not on `8000`, set `frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010
```

Mini Program:

1. Keep the backend running on `http://127.0.0.1:8000`.
2. Open `miniapp/` in WeChat DevTools.
3. For local development, keep `urlCheck` disabled in `miniapp/project.config.json`.

If your backend is running on another port, set this once in the WeChat DevTools console:

```javascript
wx.setStorageSync("foodnote_api_base", "http://127.0.0.1:8010")
```

## Environment

Copy `.env.example` to `.env` and fill a rotated local key:

```bash
MIMO_API_KEY=
MIMO_BASE_URL=
MIMO_MODEL=mimo-v2.5
ASR_MODEL=medium
ASR_DEVICE=cuda
ASR_COMPUTE_TYPE=int8
DATABASE_URL=sqlite:///./foodnote.db
STORAGE_ROOT=./storage
MAX_UPLOAD_BYTES=209715200
XHS_DOWNLOADER_COMMAND=
DOUYIN_DOWNLOADER_COMMAND=
XHS_COLLECTOR_API_BASE=
DOUYIN_COLLECTOR_API_BASE=
COLLECTOR_WORKDIR=./storage/collectors
DOUYIN_COOKIE=
YTDLP_COMMAND=
YTDLP_COOKIES_FILE=
YTDLP_COOKIES_FROM_BROWSER=
```

`MIMO_BASE_URL` should be the local/private model endpoint you use for Mimo. Keep the real URL and API key only in ignored `.env`.
`XHS_DOWNLOADER_COMMAND` is optional. When configured, it should point to a local command that accepts a URL and prints JSON metadata. If it is not configured or platform scraping fails, use the manual text/media fallback in the app.
`DOUYIN_DOWNLOADER_COMMAND` follows the same contract for Douyin.
`MAX_UPLOAD_BYTES` limits each manually uploaded image/video/audio file. The default example is 200 MB.
If the machine does not have a usable CUDA GPU, set `ASR_DEVICE=cpu` and keep `ASR_COMPUTE_TYPE=int8`. The backend will also try a CPU fallback when CUDA initialization fails.
`YTDLP_COMMAND` is an optional fallback downloader, inspired by Videdown's `yt-dlp` engine approach. Keep `YTDLP_COOKIES_FILE` and `YTDLP_COOKIES_FROM_BROWSER` empty unless you explicitly want yt-dlp to use exported cookies or a browser cookie store.

## Collector Integration

Foodnote does not vendor platform scrapers into the main app. Keep external collectors under `tools/external/` and bridge them through environment variables. This keeps platform-specific churn away from the recipe pipeline and makes it easier to replace a collector when a platform changes.

Suggested collector sources:

- Xiaohongshu: `https://github.com/JoeanAmier/XHS-Downloader`
- Douyin/TikTok: `https://github.com/Evil0ctal/Douyin_TikTok_Download_API`
- General video fallback: `https://github.com/yt-dlp/yt-dlp`, based on the same downloader engine used by `https://github.com/cshuangyy/videdown`

Install/update collector source code:

```powershell
.\scripts\install_collectors.ps1
```

Start local collector APIs and write their local base URLs into `.env`:

```powershell
.\scripts\start_collectors.ps1 -Install
```

Install optional `yt-dlp` fallback downloader:

```powershell
.\scripts\install_ytdlp.ps1
```

Use `-Install` the first time to create each collector's ignored local virtual environment and install its dependencies. Later runs can omit `-Install`. The script starts:

- XHS-Downloader API, default `http://127.0.0.1:5556`
- Douyin_TikTok_Download_API, default `http://127.0.0.1:5557`

The startup script creates Python 3.12 virtual environments for both collectors, writes logs to `storage/logs/collectors/*.log`, waits until both HTTP services are reachable, and only then writes the collector API bases into `.env`. If startup fails, read the matching `*.err.log` first.

For real Douyin links, the external collector may need a current web cookie. Put it only in local `.env` as `DOUYIN_COOKIE=...`; `start_collectors.ps1` will push it to the local Douyin collector after startup without printing it. Do not put cookies in `.env.example`, README examples, issue text, or commits.

For real Xiaohongshu links, XHS-Downloader may also need a fresh Xiaohongshu web cookie. Follow its own cookie guide and keep the value in ignored local collector settings or local `.env`; do not add real cookies to project files.

Restart the Foodnote backend after the script updates `.env`.

The backend accepts either a command or an API:

- `XHS_DOWNLOADER_COMMAND` / `DOUYIN_DOWNLOADER_COMMAND`: command that receives the source URL as the final argument and prints one JSON object.
- `XHS_COLLECTOR_API_BASE` / `DOUYIN_COLLECTOR_API_BASE`: HTTP service base URL. Foodnote calls `POST /extract` with `{ "platform": "...", "url": "..." }`.

For convenience, Foodnote also understands common native endpoints from the suggested external projects:

- XHS-Downloader: `POST /xhs/detail`
- Douyin_TikTok_Download_API: `GET /api/hybrid/video_data`

If a collector returns remote `image_urls` or `video_url` fields, Foodnote downloads those files into `COLLECTOR_WORKDIR` before sending images/frames to Mimo or running ASR.

Expected JSON fields:

```json
{
  "platform": "xiaohongshu",
  "kind": "image",
  "source_url": "https://example.com/note",
  "title": "番茄鸡蛋面",
  "author": "demo",
  "text": "正文或视频标题/描述",
  "image_paths": ["D:/code/foodnote/storage/collectors/image.jpg"],
  "video_path": null,
  "metadata": {}
}
```

`scripts/collector_bridge.py` can normalize a collector that already prints JSON:

```powershell
python scripts\collector_bridge.py xiaohongshu "https://example.com/note" --command "python path\to\collector.py" --output-dir storage\collectors
```

Platform scraping may require cookies, login, rate limits, or manual risk-control handling. Foodnote deliberately does not bypass those controls; the manual text/media fallback is part of the V1 product.

`yt-dlp` is used only as a fallback after the platform-specific collector fails or is not configured. It is useful for video links, especially when a platform extractor changes. Xiaohongshu image notes should still use `XHS-Downloader` or manual material upload because `yt-dlp` focuses on video extraction and may not return full note images.

## API Surface

- `POST /api/import-jobs`: submit a link, optional manual text, and optional uploaded media paths.
- `GET /api/import-jobs` / `GET /api/import-jobs/{id}`: inspect import status and recovery-friendly failure messages.
- `GET /api/system/status`: inspect local Mimo, ASR, ffmpeg, upload, and collector readiness.
- `GET /api/recipes` / `GET /api/recipes/random` / `GET /api/recipes/{id}`: browse and pick dishes.
- `PATCH /api/recipes/{id}`: edit dish name, description, cover, tags, ingredients, and steps.
- `GET /api/preferences` / `PATCH /api/preferences`: manage household taste preferences, default servings, and recent-dish avoidance for random picks.
- `POST /api/today-menu/items`: add a recipe with servings and note.
- `PATCH /api/today-menu/items/{id}`: update servings or note.
- `DELETE /api/today-menu/items/{id}` / `DELETE /api/today-menu/items`: remove or clear menu items.
- `GET /api/today-menu/shopping-list`: build a shopping list from selected dishes and servings.
- `POST /api/menu-orders`: confirm today's menu into a meal record and clear the active menu.
- `GET /api/menu-orders?query=` / `GET /api/menu-orders/{id}`: list, filter, and inspect recent confirmed menus.
- `POST /api/menu-orders/{id}/restore`: reuse a confirmed menu by merging its dishes back into today's menu.
- `GET /api/cooking-stats`: inspect cooking frequency and total servings by dish.
- `GET /api/weekly-plans` / `GET /api/weekly-plans/{id}`: read generated weekly menu plans.
- `POST /api/weekly-plans`: generate a preference-aware weekly plan from saved recipes.
- `POST /api/weekly-plans/items/{id}/add-to-today`: add a planned meal into today's menu.
- `DELETE /api/weekly-plans/{id}`: remove an outdated weekly plan.

## Product Flow

The Web app remains the import and editing tool. If automatic platform extraction fails, the failed job exposes a manual recovery action that reuses the original link and switches the import form into manual mode.

The Mini Program is the lightweight household menu surface: browse dishes, open recipe details, pick a preference-aware random dish, add dishes to today's menu with the household default serving count, adjust servings, leave taste/portion notes, confirm a menu, generate a weekly menu, add planned meals into today's menu, edit taste preferences, search menu history, and read shopping/history/frequency lists.

## Verification

```bash
cd backend
uv run pytest

cd ../frontend
npm run test
npm run build
```

## Roadmap

- Family menu ordering flow
- More advanced taste scoring beyond the current tag/ingredient/recent-dish preference rules
- Hardening for collector adapters, including per-platform cookie setup notes, retry queues, and clearer failed-import recovery
