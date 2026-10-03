"""Structured DB logging.

The `logs` table (LogEntry) backs the /api/v1/logs, /api/v1/logs/export
endpoints and the frontend Logs page — but until this module existed nothing
in the codebase ever wrote a row to it, so those always returned empty
results. This provides a single best-effort helper used at key download
lifecycle points (start/complete/fail/retry/cancel) so the Logs UI has real
data instead of always showing "No log entries found".
"""
import logging

from database.db_manager import AsyncSessionLocal
from database.models import LogEntry

logger = logging.getLogger("streamvault.dblog")


async def log_event(level: str, message: str, download_id: str | None = None):
    """Write a structured log row. Best-effort — a logging failure must never
    break the download/queue flow that triggered it, so all exceptions are
    swallowed (and reported only to the file/stream logger at DEBUG level)."""
    try:
        async with AsyncSessionLocal() as session:
            session.add(LogEntry(level=level.upper(), message=message, download_id=download_id))
            await session.commit()
    except Exception as exc:
        logger.debug(f"DB log write failed: {exc}")
