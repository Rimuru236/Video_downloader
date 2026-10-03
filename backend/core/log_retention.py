"""DATA-2: scheduled log-table pruning.

`logs` now actually accumulates rows in normal operation (db_logger.log_event
writes one per download-lifecycle event). `DELETE /logs` exists but nothing
calls it automatically, and the query limits in routes_logs.py cap what a
single request *returns* without capping table growth itself. This runs a
periodic age- and count-based prune so the table doesn't grow unbounded on a
long-running deployment.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from config.config_manager import ConfigManager
from database.db_manager import AsyncSessionLocal
from database.models import LogEntry

logger = logging.getLogger("streamvault.log_retention")
config = ConfigManager()


async def prune_logs() -> int:
    """Delete log rows older than log_retention_days (if >0), then trim down
    to log_retention_max_rows (if >0) by deleting the oldest excess rows.
    Returns the number of rows deleted. Either knob set to 0 disables that
    half of the prune — both at 0 disables pruning entirely."""
    deleted = 0
    try:
        retention_days = int(await config.get_async("log_retention_days", "30"))
    except ValueError:
        retention_days = 30
    try:
        max_rows = int(await config.get_async("log_retention_max_rows", "50000"))
    except ValueError:
        max_rows = 50000

    async with AsyncSessionLocal() as session:
        if retention_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            result = await session.execute(delete(LogEntry).where(LogEntry.created_at < cutoff))
            deleted += result.rowcount or 0
            await session.commit()

        if max_rows > 0:
            count = (await session.execute(select(func.count(LogEntry.id)))).scalar_one()
            excess = count - max_rows
            if excess > 0:
                # Delete the oldest `excess` rows — SQLite/Postgres both
                # support DELETE ... WHERE id IN (subquery LIMIT n).
                oldest_ids = select(LogEntry.id).order_by(LogEntry.created_at).limit(excess)
                result = await session.execute(delete(LogEntry).where(LogEntry.id.in_(oldest_ids)))
                deleted += result.rowcount or 0
                await session.commit()

    if deleted:
        logger.info(f"Log retention: pruned {deleted} row(s)")
    return deleted


async def run_log_retention_loop():
    """Runs prune_logs() on a timer until cancelled. Started/stopped
    alongside the queue manager in main.py's lifespan."""
    while True:
        try:
            interval_hours = float(await config.get_async("log_retention_interval_hours", "24"))
        except ValueError:
            interval_hours = 24
        try:
            await prune_logs()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Log retention pass failed: {exc}")
        try:
            await asyncio.sleep(max(interval_hours, 0.01) * 3600)
        except asyncio.CancelledError:
            raise
