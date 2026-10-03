"""
StreamVault — Universal Media Downloader Platform
FastAPI Backend Entry Point
"""

import asyncio
import sys
import os

# Ensure backend/ is on the path regardless of where you run from
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Also ensure working-directory paths (logs/, downloads/) land next to backend/
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)
os.chdir(_PROJECT_DIR)

import uuid
import uvicorn
from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from logging.handlers import RotatingFileHandler

from database.db_manager import init_db
from utils.ffmpeg_checker import check_ffmpeg
from utils.auth import require_api_key
from utils.rate_limiter import RateLimitMiddleware
from config.config_manager import ConfigManager

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

# OBS-1: rotate at 10MB, keep 5 backups, so a long-running deployment doesn't
# grow logs/downloader.log without bound.
_file_handler = RotatingFileHandler(
    "logs/downloader.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        _file_handler,
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("streamvault")


# ── Single-process guard (ARCH-1) ────────────────────────────────────────────
# StreamVault keeps all shared state — the download queue, the WebSocket
# progress registry, the thread pool, ConfigManager's in-memory cache — in
# this one process's memory (see README "Architecture" section). Running
# more than one worker process silently splits that state across workers
# with no error: a download submitted to worker A never shows progress on
# worker B, the queue drains inconsistently, settings written on one worker
# don't appear on another. WEB_CONCURRENCY is the env var most platforms
# (Heroku, Render, the official gunicorn/uvicorn Docker image) use to set
# worker count — if it's set above 1 we refuse to start rather than run in
# that silently-broken state. This does not catch every possible
# multi-worker invocation (a bare `uvicorn main:app --workers 4` sets no
# such env var, and nothing short of controlling the launch command can
# catch that) — it only catches the common platform-driven case. Set
# SV_ALLOW_MULTIWORKER=1 to bypass at your own risk.
_web_concurrency = os.environ.get("WEB_CONCURRENCY")
if _web_concurrency and _web_concurrency.strip().isdigit() and int(_web_concurrency) > 1 \
        and os.environ.get("SV_ALLOW_MULTIWORKER") != "1":
    raise RuntimeError(
        f"WEB_CONCURRENCY={_web_concurrency} requests multiple worker processes, but "
        "StreamVault keeps all shared state in-process and does not support that "
        "(see README 'Architecture'). Set WEB_CONCURRENCY=1, or SV_ALLOW_MULTIWORKER=1 "
        "to start anyway at your own risk."
    )


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("StreamVault starting up...")
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("config",    exist_ok=True)

    await init_db()

    from utils.auth import _warn_if_unprotected
    _warn_if_unprotected()

    if not check_ffmpeg():
        logger.warning("FFmpeg not found — merging and conversion disabled")

    from core.queue_manager import get_queue_manager
    from core.downloader_engine import shutdown_executors
    from services.metadata_service import shutdown_executor
    from core.log_retention import run_log_retention_loop

    qm = get_queue_manager()
    await qm.start()
    logger.info("Queue manager started")

    # DATA-2: periodic prune so the logs table doesn't grow unbounded.
    log_retention_task = asyncio.create_task(run_log_retention_loop())

    yield

    logger.info("StreamVault shutting down...")
    log_retention_task.cancel()
    await qm.stop()
    shutdown_executors()
    shutdown_executor()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="StreamVault API",
    description="Universal Media Downloader Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS - restrictive by default, configurable via environment
config = ConfigManager()
cors_origins = config.get("cors_origins", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins_list = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

# In development, allow localhost; in production, use specific origins
if os.environ.get("ENVIRONMENT") == "development":
    cors_origins_list = ["*"]
    # SEC-8: loud and hard to miss on purpose — ENVIRONMENT=development
    # silently overrides whatever cors_origins is configured to, which is
    # exactly right for local dev and exactly wrong if it ships that way by
    # accident.
    logger.warning(
        "ENVIRONMENT=development — CORS is wide open (allow_origins=['*']), "
        "ignoring the configured cors_origins setting. Do not set this in "
        "any deployment reachable outside your own machine."
    )

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True if cors_origins_list != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# OBS-2: request correlation IDs. Added last, after CORS/rate-limiting, so
# it ends up as the outermost middleware layer — its "before" code (assigning
# the ID) runs first on the way in, and its "after" code (stamping the
# response header) runs last on the way out, so every response gets the
# header regardless of which inner layer produced it (a normal 200, a 429
# from RateLimitMiddleware, or an error response from the handlers below).
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# OBS-2: consistent error shape everywhere — {"detail": ..., "request_id": ...}
# for both explicit HTTPExceptions (previously fine on their own, but
# inconsistent with what an unhandled exception produced) and anything
# unhandled that would otherwise fall through to FastAPI's bare default 500,
# with no way to tie a client-visible error back to the matching server log
# line. See REL-2 for a specific case (invalid status query param) that used
# to hit this gap.
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": getattr(request.state, "request_id", None)},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"Unhandled exception [request_id={request_id}] on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "request_id": request_id},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
from api.routes_downloads import router as downloads_router, ws_router as downloads_ws_router
from api.routes_queue      import router as queue_router
from api.routes_metadata   import router as metadata_router
from api.routes_settings   import router as settings_router
from api.routes_logs       import router as logs_router
from api.routes_metrics    import router as metrics_router

# All API routes require the configured api_key (see utils/auth.py) — unless
# no key is configured, in which case require_api_key() is a no-op and every
# route stays open, exactly as it behaved before auth existed. /health is
# intentionally excluded so container/orchestrator healthchecks don't need
# the key. The WebSocket router is authenticated separately inside
# ws_progress() itself (see the comment on ws_router in routes_downloads.py)
# since it can't use this header-based dependency.
_auth = [Depends(require_api_key)]
app.include_router(downloads_router,    prefix="/api/v1", tags=["downloads"], dependencies=_auth)
app.include_router(downloads_ws_router, prefix="/api/v1", tags=["downloads"])
app.include_router(queue_router,        prefix="/api/v1", tags=["queue"],     dependencies=_auth)
app.include_router(metadata_router,     prefix="/api/v1", tags=["metadata"],  dependencies=_auth)
app.include_router(settings_router,     prefix="/api/v1", tags=["settings"],  dependencies=_auth)
app.include_router(logs_router,         prefix="/api/v1", tags=["logs"],      dependencies=_auth)
app.include_router(metrics_router,      prefix="/api/v1", tags=["metrics"],   dependencies=_auth)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ARCH-5: /health only proves the process is up (liveness) — it can't tell
# an orchestrator "running" from "actually able to serve a download"
# (readiness). /ready checks the three things that would actually block a
# download from working: DB connectivity, FFmpeg presence, and disk
# headroom on the download folder.
@app.get("/ready")
async def ready():
    import shutil
    from sqlalchemy import text
    from database.db_manager import AsyncSessionLocal

    checks = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)}

    checks["ffmpeg"] = {"ok": check_ffmpeg()}

    try:
        min_free_bytes = int(config.get("ready_min_disk_bytes", "524288000"))  # 500MB
        download_folder = config.get("download_folder", "./downloads")
        usage = shutil.disk_usage(download_folder if os.path.isdir(download_folder) else ".")
        checks["disk"] = {"ok": usage.free >= min_free_bytes, "free_bytes": usage.free}
    except OSError as exc:
        checks["disk"] = {"ok": False, "error": str(exc)}

    is_ready = all(c["ok"] for c in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready", "checks": checks},
    )


@app.get("/")
async def root():
    return {"message": "StreamVault API — visit /docs for Swagger UI"}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[_BACKEND_DIR],   # only watch backend/, not the whole project
        log_level="info",
    )
