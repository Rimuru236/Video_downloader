# StreamVault — Universal Media Downloader Platform

A full-stack, production-ready media downloader built on **FastAPI + yt-dlp + React + Tailwind CSS**. Downloads from 1,000+ sites including YouTube, Vimeo, TikTok, Instagram, SoundCloud, Twitch, and more.

---

## Features

- **Download engine** — yt-dlp with FFmpeg post-processing, format selection, retry logic, exponential backoff
- **Queue manager** — async priority queue, pause/resume, concurrency control
- **Metadata extraction** — title, channel, duration, views, subtitles, formats — no download required
- **Batch downloader** — paste hundreds of URLs or import from file
- **Playlist & channel download** — full playlist support with item selection
- **Subtitle manager** — auto-generated and manual subtitles, multi-language, SRT/VTT/ASS
- **Live progress** — WebSocket real-time progress bars and speed graphs
- **Analytics dashboard** — download history, speed charts, platform breakdown, storage usage
- **Settings system** — quality, concurrency, rate limiting, proxy, cookies, audio format
- **Structured logging** — DB + file logs, exportable, filterable by level
- **CLI interface** — full terminal control with live progress watching
- **Docker support** — one-command deployment with `docker-compose up`

---

## Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Backend     | Python 3.11+, FastAPI, uvicorn      |
| Downloader  | yt-dlp, FFmpeg, aria2c (optional)   |
| Database    | SQLite (default) → PostgreSQL-ready |
| ORM         | SQLAlchemy 2.0 (async)              |
| Frontend    | React 18, Vite, Tailwind CSS 3      |
| State       | Zustand                             |
| Charts      | Chart.js 4                          |
| Container   | Docker, nginx                       |

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
git clone https://github.com/yourname/streamvault
cd streamvault
docker-compose up --build
```

Open http://localhost:3000

### Option 2 — Local Development

**Prerequisites:** Python 3.11+, Node 20+, FFmpeg

```bash
# 1. Backend
cd streamvault
pip install -r requirements.txt
python backend/main.py
# API running at http://localhost:8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
# UI running at http://localhost:3000
```

---

## CLI Usage

```bash
# Single download (starts immediately)
python cli.py download https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Download with options
python cli.py download https://youtu.be/xyz -q "bestvideo[height<=1080]+bestaudio/best" -t video --subtitles --watch

# Audio only
python cli.py download https://soundcloud.com/artist/track -t audio -a mp3

# Add to queue instead of starting immediately
python cli.py download https://vimeo.com/123456 --queue

# Batch from file
python cli.py batch urls.txt

# Batch from stdin
cat urls.txt | python cli.py batch -

# Queue management
python cli.py queue list
python cli.py queue start
python cli.py queue pause
python cli.py queue clear

# Monitor downloads
python cli.py status
python cli.py status <download-id>

# Settings
python cli.py settings get
python cli.py settings get max_concurrent
python cli.py settings set max_concurrent 6
python cli.py settings set download_folder /Volumes/Media/Downloads

# Logs
python cli.py logs
python cli.py logs --level ERROR
python cli.py logs --limit 100

# Cancel / retry
python cli.py cancel <download-id>
python cli.py retry <download-id>
```

---

## API Reference

### Downloads

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/v1/download` | Start or queue a download |
| POST   | `/api/v1/download/batch` | Batch queue multiple URLs |
| GET    | `/api/v1/downloads` | List all downloads |
| GET    | `/api/v1/download/{id}` | Get download details |
| POST   | `/api/v1/download/{id}/pause` | Pause |
| POST   | `/api/v1/download/{id}/resume` | Resume |
| POST   | `/api/v1/download/{id}/cancel` | Cancel |
| POST   | `/api/v1/download/{id}/retry` | Retry failed |
| DELETE | `/api/v1/download/{id}` | Delete |
| WS     | `/api/v1/ws/download/{id}` | Live progress stream |

### Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/v1/queue` | List queue |
| POST   | `/api/v1/queue/add` | Add to queue |
| POST   | `/api/v1/queue/start` | Start processing |
| POST   | `/api/v1/queue/pause` | Pause queue |
| POST   | `/api/v1/queue/clear` | Clear all |
| POST   | `/api/v1/queue/reorder` | Reorder item |
| DELETE | `/api/v1/queue/{id}` | Remove item |

### Metadata

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/v1/metadata` | Extract metadata from URL |
| GET    | `/api/v1/metadata/formats?url=` | List available formats |

### Settings & Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/v1/settings` | All settings |
| POST   | `/api/v1/settings/update` | Update one setting |
| POST   | `/api/v1/settings/bulk` | Update multiple |
| GET    | `/api/v1/logs` | Filtered log entries |
| GET    | `/api/v1/logs/file` | Raw log file (last 500 lines) |
| GET    | `/api/v1/logs/export` | Export all logs |
| GET    | `/api/v1/analytics/summary` | Download statistics |
| GET    | `/api/v1/analytics/detailed` | Real daily/platform/format aggregations backing the Dashboard/Analytics charts |
| GET    | `/api/v1/metrics` | Prometheus-format metrics (queue depth, active downloads, success rate, avg speed, disk space) |
| GET    | `/ready` | Readiness check — DB connectivity, FFmpeg presence, disk headroom (unlike `/health`, can return 503) |

---

## Configuration

Settings are stored in `config/config.json` and can be overridden with environment variables prefixed `SV_`:

| Key | Default | Description |
|-----|---------|-------------|
| `download_folder` | `./downloads` | Where files are saved |
| `default_quality` | `bestvideo+bestaudio/best` | yt-dlp format string |
| `max_concurrent` | `4` | Simultaneous downloads |
| `max_retries` | `5` | Retry attempts on failure |
| `retry_backoff` | `2` | Exponential backoff base (seconds) |
| `audio_format` | `mp3` | Default audio extraction format |
| `rate_limit` | `0` | Speed limit KB/s (0 = unlimited) |
| `proxy` | `` | HTTP/SOCKS proxy URL |
| `cookies_file` | `` | Path to Netscape cookies.txt |
| `use_aria2` | `false` | Use aria2c for segmented downloads |
| `subtitle_lang` | `en` | Default subtitle language |
| `embed_subtitles` | `false` | Embed subtitles in video container |
| `write_thumbnail` | `false` | Save thumbnail alongside video |
| `write_metadata` | `true` | Embed ID3/MP4 metadata tags |
| `database_url` | SQLite | Full SQLAlchemy URL for PostgreSQL |
| `api_key` | `` | Shared secret required on every API request once set (empty = no auth, open to anyone who can reach the port) |
| `additional_allowed_roots` | `` | Extra directories (comma-separated) a per-download `output_folder` override may target, besides `download_folder` |
| `api_rate_limit_per_min` | `300` | Max requests per client (per API key, else per IP) per rolling minute — `0` disables |
| `ffmpeg_timeout` | `3600` | Max seconds the hardsub burn-in ffmpeg subprocess may run before it's killed |
| `executor_max_workers` | `32` | Hard ceiling on the download thread pool — advanced knob, decoupled from `max_concurrent`; only raise it if you actually need `max_concurrent` above 32 |
| `log_retention_days` | `30` | Delete `logs` table rows older than this — `0` disables age-based pruning |
| `log_retention_max_rows` | `50000` | Trim the `logs` table down to this many rows (oldest first) — `0` disables count-based pruning |
| `log_retention_interval_hours` | `24` | How often the retention pass runs |
| `ready_min_disk_bytes` | `524288000` | `/ready` reports not-ready below this much free disk on the download folder (default 500MB) |

**Enabling authentication:** the API is unauthenticated by default (fine for a single trusted machine, not fine for anything reachable over a network you don't fully control). To require a key:

```bash
export SV_API_KEY="some-long-random-string"
python backend/main.py
```

Then, in the web UI, go to **Settings → Security** and paste the same value into "API Key" — it's stored in that browser's local storage and sent as the `X-API-Key` header (or `?api_key=` on the WebSocket connection, since browsers can't set custom headers on a WebSocket handshake). For the CLI, set `STREAMVAULT_API_KEY` in the environment instead. `/health` and `/ready` are intentionally left open so container/orchestrator healthchecks don't need the key.

**PostgreSQL migration:**
```bash
export SV_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/streamvault"
python backend/main.py
```

**Schema migrations (Alembic):** on SQLite, `init_db()` still auto-creates tables and additively adds any missing columns on startup (`_auto_migrate_sqlite` in `backend/database/db_manager.py`) — nothing changes there, it's zero-friction by design for local dev. On PostgreSQL, use Alembic instead:

```bash
# Fresh Postgres database — create the schema
export SV_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/streamvault"
alembic upgrade head

# An existing Postgres database that already has the tables (e.g. created by
# an earlier create_all() run) — baseline it without re-running DDL:
alembic stamp head
```

`alembic/env.py` reads `SV_DATABASE_URL` / `config/config.json` the same way the app does, so it always targets whatever database the app would actually connect to. When you add or change a model in `backend/database/models.py`, generate the migration with:

```bash
alembic revision --autogenerate -m "describe the change"
```

then review the generated file in `alembic/versions/` before committing — autogenerate is a starting point, not a guarantee.

---

## Project Structure

```
streamvault/
├── .github/workflows/ci.yml        # Backend pytest + frontend Vitest/build, on push/PR
├── alembic/                        # PostgreSQL schema migrations (see Configuration)
│   ├── env.py
│   └── versions/
├── alembic.ini
├── backend/
│   ├── main.py                    # FastAPI app + lifespan
│   ├── api/
│   │   ├── routes_downloads.py    # Download CRUD + WebSocket
│   │   ├── routes_queue.py        # Queue management
│   │   ├── routes_metadata.py     # URL metadata extraction
│   │   ├── routes_settings.py     # Settings CRUD
│   │   └── routes_logs.py         # Logs + analytics
│   ├── core/
│   │   ├── downloader_engine.py   # yt-dlp wrapper + retry + progress
│   │   └── queue_manager.py       # Async priority queue loop
│   ├── database/
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── db_manager.py          # Engine + session + init
│   ├── services/
│   │   └── metadata_service.py    # yt-dlp metadata extraction
│   ├── config/
│   │   └── config_manager.py      # Singleton config + env overrides
│   ├── utils/
│   │   ├── url_validator.py        # URL sanitization + security
│   │   └── ffmpeg_checker.py      # FFmpeg detection
│   └── tests/                     # pytest suite — see "Testing"
│       └── conftest.py
├── frontend/
│   ├── src/
│   │   ├── main.jsx               # React entry point
│   │   ├── App.jsx                # Root layout + page routing
│   │   ├── store/
│   │   │   └── useStore.js        # Zustand global state
│   │   ├── services/
│   │   │   └── api.js             # Typed API client + WS helper
│   │   ├── components/
│   │   │   ├── Sidebar.jsx        # Navigation sidebar
│   │   │   ├── Topbar.jsx         # Header bar
│   │   │   ├── Activity.jsx       # Live activity panel
│   │   │   ├── AddModal.jsx       # Add download modal
│   │   │   ├── Toasts.jsx         # Notification toasts
│   │   │   └── ui.jsx             # Shared primitives
│   │   └── pages/
│   │       ├── Dashboard.jsx      # Overview + charts + recent
│   │       ├── Downloads.jsx      # Full download list + filter
│   │       ├── Queue.jsx          # Queue manager
│   │       ├── Analytics.jsx      # Charts + statistics
│   │       ├── Batch.jsx          # Batch URL input
│   │       ├── Playlists.jsx      # Playlist downloader
│   │       ├── Channels.jsx       # Channel downloader
│   │       ├── Subtitles.jsx      # Subtitle manager
│   │       ├── Settings.jsx       # Settings panel
│   │       └── Logs.jsx           # Log viewer
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── cli.py                          # Terminal CLI
├── requirements.txt
├── requirements-dev.txt            # + pytest, for "Testing" — kept out of the Docker image
├── pytest.ini
├── docker-compose.yml
├── docker-compose.tls.yml          # Optional TLS override — see "TLS" section
├── Dockerfile.backend
├── Dockerfile.frontend
├── nginx.conf
├── nginx-tls.conf.example          # Optional HTTPS server block — see "TLS" section
└── README.md
```

---

## Architecture

**StreamVault is a single-process application by design.** The download queue, the in-memory WebSocket progress-hook registry, the yt-dlp thread pool, and `ConfigManager`'s cached settings all live in one process's memory — none of it is shared through the database or an external store like Redis. That's a deliberate simplicity trade-off, not an oversight, but it has a real consequence: **you cannot run more than one worker process** (`uvicorn ... --workers N` with `N>1`, or any platform that scales this app horizontally by forking multiple workers behind one port) without silently breaking it — a download submitted to one worker won't show progress, or even exist, on another.

- `python backend/main.py` (the documented entry point) always starts exactly one process — this is safe.
- If your deployment platform sets `WEB_CONCURRENCY` (Heroku, Render, the gunicorn/uvicorn Docker images) above `1`, the app refuses to start rather than run in that broken state. See the guard at the top of `backend/main.py`.
- To scale beyond one process, you'd need to move shared state to Postgres/Redis and fan out WebSocket progress via pub/sub — that's a real architectural project, not a config change, and hasn't been done here.
- Multiple independent StreamVault *instances* (each its own single process, its own database, its own port) behind a router is fine — it's specifically multiple workers sharing one app/port that breaks.

---

## Security

- All URLs are validated and sanitized before passing to yt-dlp
- Private/local IP ranges are blocked (including bracketed IPv6 literals)
- No shell interpolation — yt-dlp Python API is used directly (no subprocess)
- Per-download `output_folder` overrides are resolved and checked against an allowlisted root, rejecting `..` traversal, absolute-path overrides, and symlink escapes
- CORS is restricted to known origins in production
- Optional shared-secret API key auth (`api_key` setting / `SV_API_KEY`) — off by default; see [Configuration](#configuration)
- Per-client request rate limiting (`api_rate_limit_per_min`) — on by default at 300 req/min per API key (or per IP if no key is set); returns `429` with `Retry-After` once exceeded
- Secret-shaped settings (`api_key`, `proxy`, `cookies_file`) are masked in `GET /settings` responses — the API reports whether one is set without ever echoing the real value back; the Settings page's Proxy/Cookies fields work as replace-only (blank = leave unchanged, type a new value = replace)
- The `ffmpeg` subprocess used for hardsub burn-in has a timeout (`ffmpeg_timeout`, default 1 hour) so a hung/corrupt-input transcode can't tie up a worker thread forever; `ffmpeg -version` (the startup capability check) times out after 5s
- `ENVIRONMENT=development` logs a loud startup warning when it forces CORS wide open, so that can't ship by accident unnoticed; settings that only take effect after a process restart (`cors_origins`, `db_pool_size`, `db_max_overflow`) are flagged as `restart_required` in the settings API response

**Known limitations, honestly stated:** the URL validator checks DNS both at submission time and again immediately before yt-dlp actually fetches the URL (a download can sit queued, or wait through a retry backoff, between the two) — but not at the moment yt-dlp *follows a redirect* internally, since that happens inside yt-dlp's own HTTP client, past the point this app can intercept it. A sufficiently motivated attacker using DNS rebinding timed to that exact re-check window, or a malicious redirect chain, can still reach an internal address. There's a per-client rate limit (`api_rate_limit_per_min`, on by default) but it's in-process memory, not a hardened edge limiter. Treat this as good baseline hardening, not a guarantee against a determined, network-adjacent attacker — the trust boundary that actually matters is enabling the API key and not exposing the port beyond a network you control. For genuinely hostile-input deployments, put a network-isolated egress proxy in front of the downloader rather than relying on application-level checks alone.

---

## TLS

**The provided `docker-compose.yml` is HTTP-only.** That's fine for localhost or a private network you control, but not for anything exposed to the open internet — traffic (including the API key, once SEC-1's auth is enabled) travels in plaintext. There's no automatic TLS because there isn't a one-size-fits-right answer: it depends on your domain, your certificate issuer, and whether something else (a cloud load balancer, an existing reverse proxy) is already terminating TLS in front of this stack.

Two supported paths:

1. **Put a TLS-terminating reverse proxy in front** (Caddy, Traefik, an existing nginx/HAProxy, a cloud load balancer) that forwards plain HTTP to `frontend:8080` / `backend:8000`. Often the least work if you already run one.
2. **Terminate TLS in the provided frontend container** using `nginx-tls.conf.example` and `docker-compose.tls.yml`:

   ```bash
   # Local testing with a self-signed cert:
   mkdir -p certs
   openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
     -keyout certs/privkey.pem -out certs/fullchain.pem \
     -subj "/CN=localhost"

   # Or a real cert for a real domain — e.g. certbot in standalone mode,
   # then copy/symlink its fullchain.pem and privkey.pem into ./certs/.

   cp nginx-tls.conf.example nginx-tls.conf   # edit server_name / cert paths if needed
   docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build
   ```

   This serves plain HTTP on `:3000` (redirecting to HTTPS) and HTTPS on `:3443`. Both the frontend and backend containers already run as non-root users bound to ports above 1024 internally (see DEP-1 in the audit — `Dockerfile.frontend`, `Dockerfile.backend`), so nothing about enabling TLS needs elevated container privileges.

A self-signed cert (option 2's first variant) will trigger a browser warning — that's expected and fine for local/internal testing, not for anything public-facing.

---

## Testing

**Backend:**
```bash
pip install -r requirements-dev.txt   # adds pytest on top of requirements.txt
pytest                                 # run the whole suite (backend/tests/)
pytest backend/tests/test_auth.py -v   # a single file
```
`backend/tests/` is a real pytest suite (`conftest.py` + fixtures), isolated against a fresh temp SQLite DB and temp `config.json` for the whole session — it never touches the real project's `streamvault.db` or `config/config.json`. Covers SEC-1/2/4/5, REL-1..4, ARCH-3/4, OBS-2/3, DATA-2, and FE-2's file endpoint. `integration_test.py` and `smoke_check.py` at the project root are older hand-rolled scripts (not pytest) exercising individual functions directly — kept around, but `pytest` is the suite to run and extend going forward.

**Frontend:**
```bash
cd frontend
npm run test        # one-shot run (Vitest + React Testing Library)
npm run test:watch  # watch mode
```

**CI:** `.github/workflows/ci.yml` runs both suites (plus the frontend production build) on every push and PR — a `backend` job (installs `ffmpeg` + `requirements-dev.txt`, runs `pytest`) and a `frontend` job (`npm run test`, then `npm run build`), as separate parallel jobs so a failure in one doesn't hide the other's result.

---

## License

MIT — use freely, modify freely.
