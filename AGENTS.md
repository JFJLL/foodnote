# Foodnote Agent Rules

## Project Goal

Foodnote is a local-first food note parser and home menu tool. It turns Xiaohongshu and Douyin food notes or videos into editable recipes, then lets the user browse dishes, build today's menu, and later use a WeChat Mini Program for the same home menu flow.

## Runtime

- Use `rtk <program> ...` for real executables.
- Use `rtk pwsh -NoProfile -Command '...'` for PowerShell cmdlets, pipelines, variables, aliases, and process control.
- Backend lives in `backend/`; Web frontend lives in `frontend/`; WeChat Mini Program lives in `miniapp/`; local media and SQLite files are ignored under `storage/` and `*.db`.

## Commands

- Backend setup: `cd backend && uv venv && uv pip install -e ".[dev]"`
- Backend test: `cd backend && uv run pytest`
- Backend dev: `cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
- Frontend setup: `cd frontend && npm install`
- Frontend test/build: `cd frontend && npm run test && npm run build`
- Frontend dev: `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`

## Environment And Secrets

- Never commit `.env`, databases, downloaded media, ASR transcripts, or generated frames.
- `.env.example` may contain variable names and safe defaults only.
- Real API keys must stay in local `.env`; do not put them in README, tests, fixtures, screenshots, or commit messages.
- If a key was shared in chat or logs, treat it as exposed and rotate it before real use.
- External platform collectors live outside the main app under `tools/external/`; bridge them by command/API and normalize their output before it reaches the import pipeline.

## Product Rules

- The Web app must support Xiaohongshu and Douyin through the same import pipeline.
- The Mini Program should reuse backend recipe/menu APIs instead of duplicating parsing logic.
- AI output is always a draft. Users must be able to edit dish name, cover, ingredients, steps, tags, and source metadata.
- Import failures must give an action: retry, paste note text manually, or provide local media.
- Keep the UI as a real tool, not a marketing landing page.

## Frontend Design Rules

- Use React + TailwindCSS and lucide icons where useful.
- Use real food imagery from parsed content first; fallback gradients are only empty-state support.
- Mobile-first layout; desktop may add a right-side today's menu panel.
- Avoid large hero sections, nested cards, one-note color palettes, and text overflow.
- Visual QA must check desktop and mobile widths before handoff.

## Roadmap Notes

- Stage 2: Douyin adapter using the same import pipeline.
- Stage 3: WeChat Mini Program using the backend recipe/menu APIs.
- Stage 4: family menu workflow, portions, remarks, random picks, shopping list, taste preferences, and weekly menus. Weekly menus are implemented as local generated plans; future work should focus on richer family ordering flows and smarter scoring.
- Collector hardening: add per-platform setup guides, cookie/risk-control notes, retry queues, and a failure recovery UI without embedding scraper-specific logic into the recipe pipeline.
- Optional downloader fallback: `yt-dlp` may be configured through `YTDLP_COMMAND`, following the Videdown-style downloader-engine approach. Keep it behind platform-specific collectors because it is strongest for videos, not full Xiaohongshu image-note extraction.
