"""Prometheus-compatible metrics endpoint (OBS-3).

Hand-rolled text exposition format rather than pulling in the
`prometheus_client` package as a new dependency — everything here is a
simple point-in-time gauge computed straight from the DB and in-process
state, which doesn't need a full metrics-registry library. Same auth as the
rest of the API (see main.py) — not exempted like /health, since this leaks
more than a bare liveness check (counts, disk space). Configure your
scraper's Authorization header if `api_key` is set.
"""
import os
import shutil

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.config_manager import ConfigManager
from core.downloader_engine import active_count, progress_persist_failure_count
from database.db_manager import get_session
from database.models import Download, DownloadStatus

router = APIRouter()
config = ConfigManager()


def _gauge(name: str, help_text: str, value, labels: str = "") -> str:
    return f"# HELP {name} {help_text}\n# TYPE {name} gauge\n{name}{labels} {value}\n"


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(session: AsyncSession = Depends(get_session)):
    parts = []

    result = await session.execute(select(Download.status, func.count(Download.id)).group_by(Download.status))
    counts = {(s.value if hasattr(s, "value") else s): c for s, c in result.all()}

    body = "\n".join(f'streamvault_downloads_total{{status="{s}"}} {c}' for s, c in counts.items())
    parts.append(
        "# HELP streamvault_downloads_total Downloads grouped by current status\n"
        "# TYPE streamvault_downloads_total gauge\n" + (body + "\n" if body else "")
    )

    parts.append(_gauge(
        "streamvault_queue_depth", "Downloads currently in QUEUED status", counts.get("queued", 0),
    ))
    parts.append(_gauge(
        "streamvault_active_downloads", "Downloads with a running task in this process", active_count(),
    ))
    parts.append(_gauge(
        "streamvault_progress_persist_failures_total",
        "Cumulative count of failed progress DB writes since process start (see REL-6)",
        progress_persist_failure_count(),
    ))

    completed, failed = counts.get("completed", 0), counts.get("failed", 0)
    success_rate = round((completed / max(completed + failed, 1)) * 100, 2)
    parts.append(_gauge(
        "streamvault_download_success_rate_percent", "Success rate over completed+failed downloads", success_rate,
    ))

    avg_speed = (await session.execute(
        select(func.avg(Download.speed)).where(Download.status == DownloadStatus.DOWNLOADING, Download.speed.isnot(None))
    )).scalar() or 0
    parts.append(_gauge(
        "streamvault_download_speed_bytes_avg", "Average speed of currently-downloading items, bytes/sec", round(avg_speed, 2),
    ))

    download_folder = await config.get_async("download_folder", "./downloads")
    try:
        usage = shutil.disk_usage(download_folder if os.path.isdir(download_folder) else ".")
        parts.append(_gauge("streamvault_disk_free_bytes", "Free disk space on the download folder's filesystem", usage.free))
        parts.append(_gauge("streamvault_disk_total_bytes", "Total disk space on the download folder's filesystem", usage.total))
    except OSError:
        pass

    return "\n".join(parts)
