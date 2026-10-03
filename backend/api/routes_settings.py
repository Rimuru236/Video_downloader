"""Settings API Routes"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from database.db_manager import get_session
from database.models import Setting
from config.config_manager import ConfigManager

router = APIRouter()
config = ConfigManager()
logger = logging.getLogger("streamvault.settings")

class SettingUpdate(BaseModel):
    key: str
    value: str

# SEC-5: these keys can hold secrets (a proxy URL with embedded credentials,
# a shared API key) or filesystem paths that reveal more than they should —
# GET responses mask them rather than echoing the real value back to anyone
# who can read the settings endpoint.
SENSITIVE_KEYS = {"api_key", "proxy", "cookies_file"}
_REDACTED = "•" * 8  # "••••••••"

# SEC-8: these settings are only ever read once, at process start
# (CORSMiddleware is configured in main.py's module body; the DB connection
# pool is sized in db_manager.py's module body) — writing a new value here
# persists it correctly, but it has zero effect on the running process.
RESTART_REQUIRED_KEYS = {"cors_origins", "db_pool_size", "db_max_overflow"}


def _serialize(key: str, value: Optional[str], description: Optional[str]) -> dict:
    is_sensitive = key in SENSITIVE_KEYS
    return {
        "value": _REDACTED if (is_sensitive and value) else (value or ""),
        "description": description,
        **({"is_set": bool(value)} if is_sensitive else {}),
    }


@router.get("/settings")
async def get_all_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Setting))
    settings = result.scalars().all()
    return {s.key: _serialize(s.key, s.value, s.description) for s in settings}

@router.get("/settings/{key}")
async def get_setting(key: str, session: AsyncSession = Depends(get_session)):
    s = await session.get(Setting, key)
    if not s:
        raise HTTPException(404, f"Setting '{key}' not found")
    return {"key": s.key, **_serialize(s.key, s.value, s.description)}

@router.post("/settings/update")
async def update_setting(body: SettingUpdate, session: AsyncSession = Depends(get_session)):
    s = await session.get(Setting, body.key)
    if not s:
        s = Setting(key=body.key, value=body.value)
        session.add(s)
    else:
        s.value = body.value
    await session.commit()
    # Also write through to the in-memory/config.json-backed ConfigManager.
    # Most of the engine (yt-dlp option building, the queue loop, metadata
    # fetching) reads settings via the *synchronous* config.get(), which only
    # ever consulted config.json/env vars — never the Setting DB table. Without
    # this, saving a setting here from the UI silently had no effect on new
    # downloads until the process was restarted.
    config.set(body.key, body.value)
    restart_required = body.key in RESTART_REQUIRED_KEYS
    if restart_required:
        logger.warning(f"Setting '{body.key}' changed but requires a process restart to take effect")
    return {"key": body.key, "value": body.value, "restart_required": restart_required}

@router.post("/settings/bulk")
async def bulk_update(updates: dict[str, str], session: AsyncSession = Depends(get_session)):
    for key, value in updates.items():
        s = await session.get(Setting, key)
        if s:
            s.value = value
        else:
            session.add(Setting(key=key, value=value))
    await session.commit()
    # Keep the synchronous config path (config.json + in-memory cache) in
    # sync with what's persisted to the DB — see comment in update_setting().
    config.set_many(updates)
    restarted_keys = sorted(RESTART_REQUIRED_KEYS & updates.keys())
    if restarted_keys:
        logger.warning(f"Settings changed but require a process restart to take effect: {restarted_keys}")
    return {"updated": list(updates.keys()), "restart_required_keys": restarted_keys}
