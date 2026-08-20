# lifestats

Personal food & fitness tracking PWA. Single-user (Adnan), no build step, no framework.

## Architecture

- **Frontend**: `frontend/index.html` — one large vanilla HTML/CSS/JS file (this is the entire app UI, ~300KB). Plus `storage.js` (data layer helpers), `manifest.json` + `sw.js` (PWA/offline), `icon-512.png`.
- **Backend**: `backend/app.py` — single Flask app with all routes (food search, meals, event-types, categories, events, goals, iOS Health webhook). Also serves the frontend statically (`static_folder='../frontend'`) for local dev.
- **Data layer**: two separate connections, don't confuse them:
  - `backend/db.py` — raw `psycopg2` connection to Supabase Postgres via `POSTGRES_URL`. This is the primary data store (meals, events, goals, categories, etc.).
  - `backend/supabase_client.py` — Supabase client SDK using `FOOD_CACHE_SUPABASE_URL` / `FOOD_CACHE_SUPABASE_SERVICE_ROLE_KEY`. Used only for the `search_cache` and `food_cache` tables (USDA/FatSecret search result caching + custom foods).
- **Remote API**: `backend/agent_api.py` — a Flask blueprint mounted at `/api/agent/*`, registered in `app.py` right after `CORS(app)`. Key-protected read/write access for things outside the browser (a Claude skill, curl). Not used by the frontend. Two invariants: every route is behind `@require_key`, and every route touching user data calls `require_user()`, which 404s unknown ids — there is no users table, so an unchecked write would invent a user. Skill definition lives in `skills/lifestats/SKILL.md`.
- **External APIs**: USDA FoodData Central (`USDA_API_KEY`, falls back to `DEMO_KEY`), and a FatSecret proxy at a hardcoded Railway URL in `app.py`.

## Deployment (Vercel)

- `api/index.py` is the Vercel Python serverless entrypoint. It just imports `app` from `backend/app.py` and re-exports it — do not duplicate route logic here.
- `vercel.json`:
  - `"framework": null` — required, otherwise Vercel misdetects this as a Flask preset and prod 404s. Don't remove this.
  - Rewrites `/api/(.*)` → `/api/index.py` (Flask handles all API routes)
  - Rewrites `/(.*)` → `/frontend/$1` (everything else served as static frontend)
- Project already linked (`.vercel/project.json`, project `lifestats`). Vercel CLI is not installed globally — install with `npm i -g vercel` if deploying directly via CLI instead of git push.
- Git remote: `github.com/AdnanKapadia/lifestats`, deploys from `main`.
- To ship a change: commit + push to `main` (Vercel auto-deploys), or `vercel --prod` if CLI is set up.

## Local dev

```bash
cd backend
pip3 install -r requirements.txt
python3 app.py
```
Runs on `http://localhost:5000`, serving both API and frontend. Needs `POSTGRES_URL` set (and optionally `USDA_API_KEY`, `FOOD_CACHE_SUPABASE_URL`, `FOOD_CACHE_SUPABASE_SERVICE_ROLE_KEY`, `LIFESTATS_API_KEY`, `LIFESTATS_DEFAULT_TZ`) — via `backend/.env` (gitignored) or Vercel env pull.

## Conventions / gotchas

- No build tooling — editing `frontend/index.html` directly changes the deployed UI. There's no minification or bundling to worry about.
- `backend/app.py` is large and monolithic; routes are grouped by resource (search-food, meals, event-types, categories, events, goals, integrations). Follow the existing route/response shape when adding new ones rather than introducing new patterns.
- Several `backend/*.py` files (`debug_*.py`, `test_*.py`, `verify_schema.py`, `insert_steps.py`, `trigger_cleanup.py`) are one-off scripts, not part of the served app — don't wire them into `app.py`.
- Root-level `test_favorites.py` and `debug_check_deleted.py` are standalone scripts too.
- Don't commit secrets — `.env`, `backend/.env`, and `.env*` are gitignored; use Vercel's env var dashboard/CLI for prod config.
- Timestamps everywhere (`meals.timestamp`, `events.timestamp`) are epoch **milliseconds** in UTC, stored as BIGINT. The older routes take a `timezoneOffset` in minutes (JS `getTimezoneOffset()` convention); `/api/agent/*` instead takes an IANA `tz` name and uses `zoneinfo`, which is why `tzdata` is in `requirements.txt`.
- `events.data` is unconstrained JSONB. A misspelled field name writes a row that looks saved but never shows up in charts, since `get_chart_data` extracts by field name — validate against the event type's `field_schema` before inserting.
