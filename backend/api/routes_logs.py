"""Logs API Routes"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, case
from typing import Optional
from database.db_manager import get_session
from database.models import LogEntry, Download, DownloadStatus
from config.config_manager import ConfigManager
import os

config = ConfigManager()
_LOG_EXPORT_LIMIT = int(config.get("log_export_limit", "10000"))
_LOG_QUERY_LIMIT = int(config.get("log_query_limit", "1000"))

router = APIRouter()

@router.get("/logs")
async def get_logs(
    level:       Optional[str] = None,
    download_id: Optional[str] = None,
    limit:       int = 200,
    offset:      int = 0,
    session: AsyncSession = Depends(get_session),
):
    # Enforce configurable limits to prevent memory issues
    limit = min(limit, _LOG_QUERY_LIMIT)
    offset = max(offset, 0)
    
    q = select(LogEntry).order_by(desc(LogEntry.created_at)).limit(limit).offset(offset)
    if level:
        q = q.where(LogEntry.level == level.upper())
    if download_id:
        q = q.where(LogEntry.download_id == download_id)
    result = await session.execute(q)
    logs = result.scalars().all()
    return [{"id": l.id, "level": l.level, "message": l.message,
             "download_id": l.download_id, "created_at": l.created_at.isoformat()} for l in logs]

@router.get("/logs/file", response_class=PlainTextResponse)
async def get_log_file():
    path = "logs/downloader.log"
    if not os.path.exists(path):
        return "No log file found."
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(lines[-500:])   # last 500 lines

@router.get("/logs/export", response_class=PlainTextResponse)
async def export_logs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LogEntry).order_by(LogEntry.created_at).limit(_LOG_EXPORT_LIMIT))
    logs = result.scalars().all()
    return "\n".join(f"{l.created_at} [{l.level}] {l.message}" for l in logs)

@router.delete("/logs")
async def clear_logs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LogEntry))
    for l in result.scalars().all():
        await session.delete(l)
    await session.commit()
    return {"cleared": True}

@router.get("/analytics/summary")
async def analytics_summary(session: AsyncSession = Depends(get_session)):
    from sqlalchemy import func
    
    # Combine multiple aggregations into a single query for better performance
    result = await session.execute(
        select(
            func.count(Download.id).label('total'),
            func.sum(case((Download.status == DownloadStatus.DOWNLOADING, 1), else_=0)).label('active'),
            func.sum(case((Download.status == DownloadStatus.COMPLETED, 1), else_=0)).label('completed'),
            func.sum(case((Download.status == DownloadStatus.FAILED, 1), else_=0)).label('failed'),
            func.sum(case((Download.status == DownloadStatus.COMPLETED, Download.filesize), else_=0)).label('total_bytes')
        )
    )
    row = result.one()
    
    total = row.total or 0
    active = row.active or 0
    done = row.completed or 0
    failed = row.failed or 0
    total_bytes = row.total_bytes or 0

    return {
        "total":       total,
        "active":      active,
        "completed":   done,
        "failed":      failed,
        "total_bytes": total_bytes,
        "success_rate": round((done / max(done + failed, 1)) * 100, 1),
    }


@router.get("/analytics/detailed")
async def analytics_detailed(session: AsyncSession = Depends(get_session)):
    """OBS-4: real aggregations backing the Dashboard/Analytics charts,
    which previously rendered Math.random() on every render regardless of
    what was actually in the database."""
    from sqlalchemy import func
    from datetime import datetime, timedelta, timezone

    # Daily download count + bytes, last 30 days. func.date() is standard
    # SQL, supported by both SQLite and PostgreSQL — no dialect branching
    # needed. Zero-filled below for days with no activity, since GROUP BY
    # only returns rows for days that actually have some.
    since = datetime.now(timezone.utc) - timedelta(days=29)
    daily_result = await session.execute(
        select(
            func.date(Download.created_at).label("day"),
            func.count(Download.id).label("count"),
            func.sum(case((Download.status == DownloadStatus.COMPLETED, Download.filesize), else_=0)).label("bytes"),
        )
        .where(Download.created_at >= since)
        .group_by(func.date(Download.created_at))
    )
    by_day = {row.day: {"count": row.count or 0, "bytes": row.bytes or 0} for row in daily_result.all()}
    daily = []
    for i in range(30):
        day = (since + timedelta(days=i)).date().isoformat()
        entry = by_day.get(day, {"count": 0, "bytes": 0})
        daily.append({"date": day, "count": entry["count"], "bytes": entry["bytes"]})

    platform_result = await session.execute(
        select(Download.source_site, func.count(Download.id))
        .where(Download.source_site.isnot(None))
        .group_by(Download.source_site)
        .order_by(func.count(Download.id).desc())
        .limit(10)
    )
    platforms = [{"site": site, "count": count} for site, count in platform_result.all()]

    # No single "format" column — video downloads use container_format,
    # audio-only ones use audio_format. Coalesce whichever applies.
    format_col = func.coalesce(Download.container_format, Download.audio_format)
    format_result = await session.execute(
        select(format_col, func.count(Download.id))
        .where(format_col.isnot(None))
        .group_by(format_col)
        .order_by(func.count(Download.id).desc())
        .limit(10)
    )
    formats = [{"format": fmt, "count": count} for fmt, count in format_result.all()]

    # Not a true "peak observed at any instant" (that would need tracking a
    # running max per download, a schema change out of scope here) — this is
    # the highest value ever persisted to Download.speed, which is the most
    # recent progress-hook reading per download. Real data, honestly labeled
    # as "highest recorded" rather than a specific "yesterday" claim the app
    # has no way to actually back up.
    peak_speed = (await session.execute(select(func.max(Download.speed)))).scalar() or 0

    return {"daily": daily, "platforms": platforms, "formats": formats, "peak_speed": peak_speed}
