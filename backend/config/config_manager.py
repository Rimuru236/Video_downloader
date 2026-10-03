"""Config Manager — reads from config/config.json with env var overrides, with database fallback"""
import json
import os
from pathlib import Path
import asyncio

CONFIG_PATH = Path("config/config.json")

_DEFAULTS = {
    "database_url":        "sqlite+aiosqlite:///./streamvault.db",
    "download_folder":     "./downloads",
    "max_concurrent":      "4",
    "max_retries":         "5",
    "retry_backoff":       "2",
    "default_quality":     "bv*[vcodec^=avc]+ba[acodec^=mp4a]/bv*[vcodec^=avc]+ba/bv*[ext=mp4]+ba/bv+ba/best",
    "audio_format":        "mp3",
    "rate_limit":          "0",
    "proxy":               "",
    "cookies_file":        "",
    "write_thumbnail":     "false",
    "write_metadata":      "true",
    "embed_subtitles":     "false",
    "subtitle_lang":       "en",
    "use_aria2":           "false",
    "cors_origins":        "http://localhost:3000,http://127.0.0.1:3000",
    "db_pool_size":        "5",
    "db_max_overflow":     "10",
    "progress_throttle":   "2",               # Progress update throttle interval (seconds)
    "metadata_cache_ttl":  "300",             # Metadata cache TTL (seconds)
    "metadata_cache_size": "1000",            # Max cache entries before cleanup
    "ws_keepalive":        "20",              # WebSocket keep-alive interval (seconds)
    "frontend_poll":       "15",              # Frontend polling interval (seconds)
    "log_export_limit":    "10000",           # Max log entries in export
    "log_query_limit":     "1000",            # Max log entries per query
    "socket_timeout":      "15",              # Network socket timeout (seconds) for downloads and metadata
    "subtitle_batch_limit": "200",            # Max videos expanded per playlist/channel subtitle batch
    "additional_allowed_roots": "",           # Extra directories (comma-separated) a per-download output_folder may target, besides download_folder
    "api_key":             "",                # Shared secret required in X-API-Key (or ?api_key=) — empty disables auth
    "api_rate_limit_per_min": "300",          # Max requests per client (per API key, else per IP) per rolling minute — 0 disables
    "ffmpeg_timeout":      "3600",            # Max seconds for the hardsub burn-in ffmpeg subprocess before it's killed
    "executor_max_workers": "32",             # Hard ceiling on the download thread pool — decoupled from max_concurrent, see ARCH-3
    "log_retention_days":      "30",          # Delete log rows older than this many days — 0 disables age-based pruning
    "log_retention_max_rows":  "50000",       # Trim the logs table down to this many rows — 0 disables count-based pruning
    "log_retention_interval_hours": "24",     # How often the retention pass runs
    "ready_min_disk_bytes": "524288000",      # /ready reports not-ready below this much free disk on the download folder (default 500MB)
    "deno_path":           "",                # Path to Deno executable for yt-dlp JavaScript runtime (empty = auto-detect from PATH)
}

class ConfigManager:
    _instance = None
    _data: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self._data = dict(_DEFAULTS)
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH) as f:
                    file_cfg = json.load(f)
                self._data.update(file_cfg)
            except Exception:
                pass
        # Env var overrides (SV_KEY=value)
        for key in list(self._data.keys()):
            env = os.environ.get(f"SV_{key.upper()}")
            if env is not None:
                self._data[key] = env

    def get(self, key: str, default: str = "") -> str:
        # Check env vars first (highest priority)
        env = os.environ.get(f"SV_{key.upper()}")
        if env is not None:
            return env
        # Fall back to in-memory config
        return self._data.get(key, default)

    def get_sync(self, key: str, default: str = "") -> str:
        """Synchronous get (does not query database)"""
        return self.get(key, default)

    async def get_async(self, key: str, default: str = "") -> str:
        """Async get that also checks database (for settings persisted via API)"""
        # Check env vars first
        env = os.environ.get(f"SV_{key.upper()}")
        if env is not None:
            return env

        # Check database for persisted settings
        try:
            from database.db_manager import AsyncSessionLocal
            from database.models import Setting
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Setting).where(Setting.key == key))
                setting = result.scalar_one_or_none()
                if setting and setting.value:
                    return setting.value
        except Exception:
            pass

        # Fall back to in-memory config
        return self._data.get(key, default)

    def set(self, key: str, value: str):
        """Update in-memory and persist to config.json"""
        self._data[key] = value
        self._flush()

    def set_many(self, updates: dict):
        """Update multiple keys in-memory and persist once (avoids one disk
        write per key when saving a whole settings form)."""
        self._data.update(updates)
        self._flush()

    def _flush(self):
        CONFIG_PATH.parent.mkdir(exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(self._data, f, indent=2)
