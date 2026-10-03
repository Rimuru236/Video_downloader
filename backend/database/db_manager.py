"""
Database manager — async SQLAlchemy with SQLite (upgradeable to PostgreSQL)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from database.models import Base, Setting
from config.config_manager import ConfigManager
import logging

logger = logging.getLogger("streamvault.db")

config = ConfigManager()

DATABASE_URL = config.get("database_url", "sqlite+aiosqlite:///./streamvault.db")

# Configure connection pool settings for better resource management
pool_size = int(config.get("db_pool_size", "5"))
max_overflow = int(config.get("db_max_overflow", "10"))

create_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if "sqlite" in DATABASE_URL:
    # aiosqlite/SQLite uses a NullPool; do not pass pool sizing args
    create_kwargs["connect_args"] = {"check_same_thread": False}
else:
    create_kwargs.update({
        "pool_size": pool_size,
        "max_overflow": max_overflow,
    })

engine = create_async_engine(
    DATABASE_URL,
    **create_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

DEFAULT_SETTINGS = {
    "download_folder":     ("./downloads",    "Default download directory"),
    "default_quality":     ("bv*[vcodec^=avc]+ba[acodec^=mp4a]/bv*[vcodec^=avc]+ba/bv*[ext=mp4]+ba/bv+ba/best", "yt-dlp format string (prefers H.264/MP4 video + compatible audio)"),
    "audio_format":        ("mp3",            "Default audio output format"),
    "max_concurrent":      ("4",              "Max simultaneous downloads"),
    "max_retries":         ("5",              "Retry attempts on failure"),
    "retry_backoff":       ("2",              "Exponential backoff base (seconds)"),
    "subtitle_lang":       ("en",             "Default subtitle language"),
    "embed_subtitles":     ("false",          "Embed subtitles in container"),
    "write_thumbnail":     ("false",          "Save thumbnail alongside video"),
    "write_metadata":      ("true",           "Embed metadata tags"),
    "use_aria2":           ("false",          "Use aria2c for segmented downloads"),
    "theme":               ("system",         "UI theme: light/dark/system"),
    "rate_limit":          ("0",              "Speed limit in KB/s (0 = unlimited)"),
    "proxy":               ("",               "HTTP/SOCKS proxy URL"),
    "cookies_file":        ("",               "Path to cookies.txt for auth"),
    "cors_origins":        ("http://localhost:3000,http://127.0.0.1:3000", "CORS allowed origins (comma-separated)"),
    "db_pool_size":        ("5",              "Database connection pool size"),
    "db_max_overflow":     ("10",             "Database connection pool max overflow"),
    "additional_allowed_roots": ("",          "Extra directories (comma-separated) a per-download output_folder may target"),
    "api_key":             ("",               "Shared secret required to call the API (X-API-Key header) — empty disables auth"),
    "api_rate_limit_per_min": ("300",         "Max requests per client per rolling minute (per API key, else per IP) — 0 disables"),
    "deno_path":           ("",               "Path to Deno executable for yt-dlp JavaScript runtime (empty = auto-detect from PATH)"),
}


async def _auto_migrate_sqlite(conn):
    """Additive-only schema sync: add any model columns missing from the live
    SQLite tables. `create_all()` only creates missing tables, so on an
    existing database (already has data) newly added model columns would
    otherwise never appear and every query touching them would fail."""
    for table in Base.metadata.sorted_tables:
        result = await conn.execute(text(f"PRAGMA table_info({table.name})"))
        rows = result.fetchall()
        if not rows:
            continue  # table didn't exist before create_all() — it's fresh, nothing to migrate
        existing_cols = {row[1] for row in rows}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            col_type = column.type.compile(dialect=conn.dialect)
            await conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"))
            logger.info(f"DB migration: added column {table.name}.{column.name}")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in DATABASE_URL:
            await _auto_migrate_sqlite(conn)
    async with AsyncSessionLocal() as session:
        for key, (value, desc) in DEFAULT_SETTINGS.items():
            result = await session.get(Setting, key)
            if result is None:
                session.add(Setting(key=key, value=value, description=desc))
        await session.commit()
    logger.info(f"Database initialised: {DATABASE_URL}")


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
