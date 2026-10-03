"""
Download API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging

from database.db_manager import get_session
from database.models import Download, DownloadStatus, DownloadType, QueueItem
from core.downloader_engine import start_download, cancel_download, pause_download, register_progress_hook, unregister_progress_hook, is_active
from core.queue_manager import get_queue_manager
from services.metadata_service import extract_metadata, extract_playlist_entries
from utils.url_validator import validate_url
from utils.path_validator import validate_output_folder
from utils.auth import ws_api_key_ok
from config.config_manager import ConfigManager
import json
import os
import uuid

config = ConfigManager()
_WS_KEEPALIVE_INTERVAL = int(config.get("ws_keepalive", "20"))

logger = logging.getLogger("streamvault.routes.downloads")
router = APIRouter()
# The WebSocket route lives on its own router (see main.py) because it can't
# use the same header-based `require_api_key` dependency the HTTP routes on
# `router` use — browsers can't attach custom headers to a WebSocket
# handshake, so its key has to travel as a query param instead (checked
# manually in ws_progress() via ws_api_key_ok()).
ws_router = APIRouter()


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class DownloadCreate(BaseModel):
    url: str
    quality:       Optional[str]  = "bestvideo+bestaudio/best"
    download_type: Optional[str]  = "video"
    audio_format:  Optional[str]  = None
    subtitles:     bool = False
    subtitle_langs:  Optional[str]  = None   # comma-separated codes, e.g. "en,fr"
    subtitle_format: Optional[str]  = None   # srt/vtt/ass/lrc
    subtitle_auto:   bool = False            # include auto-generated captions
    embed_subtitles: Optional[bool] = None   # None = use global config default
    hardsub:         bool = False            # burn subtitles into the video instead of soft-embedding
    thumbnail_dl:  bool = False
    output_folder: Optional[str]  = None
    container_format: Optional[str] = None   # mp4/mkv/webm — overrides the merge_output_format default
    write_metadata:   Optional[bool] = None  # None = use global config default
    playlist_items:   Optional[str]  = None  # yt-dlp playlist_items spec, e.g. "1-50" or "1,3,5-9"
    playlist_end:     Optional[int]  = None  # cap on number of items (channel/playlist "Max Videos")
    date_after:       Optional[str]  = None  # yt-dlp dateafter spec, e.g. "20240101"
    priority:      int  = 5
    add_to_queue:  bool = False


class BatchCreate(BaseModel):
    urls:          list[str]
    quality:       Optional[str] = "bestvideo+bestaudio/best"
    download_type: Optional[str] = "video"
    audio_format:  Optional[str] = None
    subtitles:     bool = False
    add_to_queue:  bool = True


class SubtitleBatchCreate(BaseModel):
    url: str                                 # playlist or channel URL
    subtitle_langs:  Optional[str]  = None
    subtitle_format: Optional[str]  = None
    subtitle_auto:   bool = False
    embed_subtitles: Optional[bool] = None
    hardsub:         bool = False
    limit: Optional[int] = None              # safety valve for huge channels; falls back to config default


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/download")
async def create_download(
    body: DownloadCreate,
    session: AsyncSession = Depends(get_session),
):
    # Validate URL before processing
    is_valid, reason = validate_url(body.url)
    if not is_valid:
        raise HTTPException(400, f"Invalid URL: {reason}")

    # Validate output_folder before processing — without this, a client could
    # point downloads (and their ffmpeg-postprocessed output) at any path the
    # server process can write to. Resolve it to the canonical path so the
    # value actually used downstream is the one that was checked, not the
    # client's original (potentially differently-cased/relative) spelling.
    if body.output_folder:
        allowed_roots = [await config.get_async("download_folder", "./downloads")]
        extra_roots = await config.get_async("additional_allowed_roots", "")
        allowed_roots += [r.strip() for r in extra_roots.split(",") if r.strip()]
        ok, result = validate_output_folder(body.output_folder, allowed_roots)
        if not ok:
            raise HTTPException(400, f"Invalid output_folder: {result}")
        body.output_folder = result

    try:
        meta = await extract_metadata(body.url)
    except Exception as exc:
        logger.warning(f"Metadata fetch failed for {body.url}: {exc}")
        meta = {}

    # Validate download_type before creating Download object
    try:
        download_type = DownloadType(body.download_type)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Invalid download_type: {body.download_type}. Must be one of: video, audio, playlist, channel, subtitle")
    
    dl = Download(
        url=          body.url,
        title=        meta.get("title"),
        channel=      meta.get("channel") or meta.get("uploader"),
        duration=     meta.get("duration"),
        view_count=   meta.get("view_count"),
        thumbnail=    meta.get("thumbnail"),
        source_site=  meta.get("extractor"),
        quality=      body.quality,
        download_type=download_type,
        audio_format= body.audio_format,
        subtitles=    body.subtitles,
        subtitle_langs=  body.subtitle_langs,
        subtitle_format= body.subtitle_format,
        subtitle_auto=   body.subtitle_auto,
        embed_subtitles= body.embed_subtitles,
        hardsub=         body.hardsub,
        thumbnail_dl= body.thumbnail_dl,
        output_folder=body.output_folder,
        container_format=body.container_format,
        write_metadata=  body.write_metadata,
        playlist_items=  body.playlist_items,
        playlist_end=    body.playlist_end,
        date_after=      body.date_after,
        priority=     body.priority,
        status=       DownloadStatus.QUEUED if body.add_to_queue else DownloadStatus.PENDING,
    )
    session.add(dl)
    await session.commit()
    await session.refresh(dl)

    if body.add_to_queue:
        await get_queue_manager().add(dl.id, body.priority)
    else:
        await start_download(dl.id)

    return {"id": dl.id, "status": dl.status, "title": dl.title}


@router.post("/download/batch")
async def batch_download(
    body: BatchCreate,
    session: AsyncSession = Depends(get_session),
):
    # Validate download_type before processing
    try:
        download_type = DownloadType(body.download_type)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Invalid download_type: {body.download_type}. Must be one of: video, audio, playlist, channel, subtitle")
    
    # Build and commit every row in one transaction first — queuing each one
    # (`qm.add`) opens its own DB session/connection, and calling that while
    # this session's transaction is still open causes SQLite to report
    # "database is locked" once more than a couple of rows are involved.
    ids = []
    for url in body.urls:
        # Validate each URL
        is_valid, reason = validate_url(url)
        if not is_valid:
            logger.warning(f"Skipping invalid URL in batch: {url} - {reason}")
            continue

        dl = Download(
            id=           str(uuid.uuid4()),
            url=          url,
            quality=      body.quality,
            download_type=download_type,
            audio_format= body.audio_format,
            subtitles=    body.subtitles,
            status=       DownloadStatus.QUEUED,
        )
        session.add(dl)
        ids.append(dl.id)
    await session.commit()

    qm = get_queue_manager()
    for dl_id in ids:
        await qm.add(dl_id)
    return {"created": len(ids), "ids": ids}


@router.post("/download/subtitles/batch")
async def batch_subtitle_download(
    body: SubtitleBatchCreate,
    session: AsyncSession = Depends(get_session),
):
    """Expand a playlist/channel URL into one subtitle-only Download per
    video, queued individually — each behaves exactly like a single
    download_type="subtitle" request (see create_download)."""
    is_valid, reason = validate_url(body.url)
    if not is_valid:
        raise HTTPException(400, f"Invalid URL: {reason}")

    default_limit = int(config.get("subtitle_batch_limit", "200"))
    limit = body.limit if body.limit and body.limit > 0 else default_limit

    try:
        playlist = await extract_playlist_entries(body.url, limit)
    except Exception as exc:
        raise HTTPException(400, f"Could not read playlist/channel: {exc}")

    entries = playlist.get("entries") or []
    if not entries:
        raise HTTPException(400, "No videos found — is this actually a playlist or channel URL?")

    # Commit every row first, then queue — see comment in batch_download()
    # about why interleaving qm.add() with an open transaction deadlocks SQLite.
    ids = []
    for entry in entries:
        dl = Download(
            id=              str(uuid.uuid4()),
            url=             entry["url"],
            title=           entry.get("title"),
            download_type=   DownloadType.SUBTITLE,
            subtitles=       True,
            subtitle_langs=  body.subtitle_langs,
            subtitle_format= body.subtitle_format,
            subtitle_auto=   body.subtitle_auto,
            embed_subtitles= body.embed_subtitles,
            hardsub=         body.hardsub,
            status=          DownloadStatus.QUEUED,
        )
        session.add(dl)
        ids.append(dl.id)
    await session.commit()

    qm = get_queue_manager()
    for dl_id in ids:
        await qm.add(dl_id)

    total_available = playlist.get("entry_count_total", len(entries))
    return {
        "created":         len(ids),
        "ids":             ids,
        "playlist_title":  playlist.get("title"),
        "total_available": total_available,
        "truncated":       total_available > len(entries),
    }


@router.get("/downloads")
async def list_downloads(
    status: Optional[str] = None,
    limit:  int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    q = select(Download).order_by(desc(Download.created_at)).limit(limit).offset(offset)
    if status:
        try:
            status_enum = DownloadStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in DownloadStatus)
            raise HTTPException(400, f"Invalid status '{status}'. Must be one of: {valid}")
        q = q.where(Download.status == status_enum)
    result = await session.execute(q)
    downloads = result.scalars().all()
    return [_dl_to_dict(d) for d in downloads]


@router.get("/download/{download_id}")
async def get_download(
    download_id: str,
    session: AsyncSession = Depends(get_session),
):
    dl = await session.get(Download, download_id)
    if not dl:
        raise HTTPException(404, "Download not found")
    return _dl_to_dict(dl)


@router.post("/download/{download_id}/pause")
async def pause(download_id: str):
    await pause_download(download_id)
    return {"status": "paused"}


@router.post("/download/{download_id}/resume")
async def resume(download_id: str, session: AsyncSession = Depends(get_session)):
    dl = await session.get(Download, download_id)
    if not dl:
        raise HTTPException(404, "Download not found")
    # REL-1: without this, two rapid clicks (or a retried client request)
    # could each pass the check above and both call start_download(), racing
    # two yt-dlp processes against the same output file.
    if is_active(download_id):
        raise HTTPException(409, "Download is already running")
    dl.status = DownloadStatus.DOWNLOADING
    await session.commit()
    await start_download(download_id)
    return {"status": "resumed"}


@router.post("/download/{download_id}/cancel")
async def cancel(download_id: str):
    await cancel_download(download_id)
    return {"status": "cancelled"}


@router.post("/download/{download_id}/retry")
async def retry(download_id: str, session: AsyncSession = Depends(get_session)):
    dl = await session.get(Download, download_id)
    if not dl:
        raise HTTPException(404, "Download not found")
    if is_active(download_id):  # REL-1 — same duplicate-start guard as resume()
        raise HTTPException(409, "Download is already running")
    dl.status      = DownloadStatus.DOWNLOADING
    dl.error_msg   = None
    dl.retry_count = 0
    await session.commit()
    await start_download(download_id)
    return {"status": "retrying"}


@router.get("/download/{download_id}/file")
async def get_download_file(
    download_id: str,
    session: AsyncSession = Depends(get_session),
):
    """FE-2: 'Open file' was previously a dead button — there was no backend
    endpoint to serve the file at all. file_path is only populated once a
    download reaches at least one postprocessor 'finished' event (see
    downloader_engine._make_postprocessor_hook / REL-3), so a still-running
    or pre-REL-3 download correctly 404s here rather than serving nothing."""
    dl = await session.get(Download, download_id)
    if not dl:
        raise HTTPException(404, "Download not found")
    if not dl.file_path or not os.path.exists(dl.file_path):
        raise HTTPException(404, "No file available for this download")
    return FileResponse(dl.file_path, filename=os.path.basename(dl.file_path))


@router.delete("/download/{download_id}")
async def delete_download(
    download_id: str,
    delete_files: bool = False,
    session: AsyncSession = Depends(get_session),
):
    dl = await session.get(Download, download_id)
    if not dl:
        raise HTTPException(404, "Download not found")
    await cancel_download(download_id)
    # REL-3: opt-in (default False) — removing the DB row alone previously
    # left any partially- or fully-downloaded file on disk with nothing left
    # pointing to it anywhere in the app. file_path is only populated for
    # downloads that reached at least one postprocessor 'finished' event
    # (see downloader_engine._make_postprocessor_hook), so a cancelled/failed
    # download with no captured path is silently a no-op here, not an error.
    file_deleted = False
    if delete_files and dl.file_path:
        try:
            if os.path.exists(dl.file_path):
                os.remove(dl.file_path)
                file_deleted = True
        except OSError as exc:
            logger.warning(f"Could not delete file for {download_id}: {exc}")
    await session.delete(dl)
    await session.commit()
    return {"deleted": True, "file_deleted": file_deleted}


# ──────────────────────────────────────────────
# WebSocket — live progress
# ──────────────────────────────────────────────

@ws_router.websocket("/ws/download/{download_id}")
async def ws_progress(websocket: WebSocket, download_id: str):
    if not ws_api_key_ok(websocket):
        # Reject before accept() -> the ASGI server responds to the
        # handshake with HTTP 403 instead of completing the WS upgrade.
        await websocket.close(code=1008)
        return
    await websocket.accept()
    import asyncio

    async def push(payload: dict):
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            pass

    register_progress_hook(download_id, push)

    # REL-5: without actively reading incoming frames, a client disconnect
    # wasn't noticed until the next keepalive ping's send() happened to fail
    # — up to ws_keepalive seconds (20s default) of a stale, silently-dead
    # registration. A close/disconnect is only reliably observed by a
    # receive() call, not a send() — so run a receive loop concurrently
    # with the ping loop; whichever notices the disconnect first wins.
    async def receiver():
        while True:
            await websocket.receive_text()  # client only ever sends {"type":"pong"}; content is irrelevant, only presence/disconnect matters

    async def pinger():
        while True:
            await asyncio.sleep(_WS_KEEPALIVE_INTERVAL)
            await websocket.send_json({"type": "ping"})

    receiver_task = asyncio.create_task(receiver())
    pinger_task = asyncio.create_task(pinger())
    try:
        done, pending = await asyncio.wait(
            {receiver_task, pinger_task}, return_when=asyncio.FIRST_EXCEPTION
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.debug(f"[{download_id}] WS loop ended: {exc}")
    finally:
        unregister_progress_hook(download_id)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _dl_to_dict(dl: Download) -> dict:
    return {
        "id":           dl.id,
        "url":          dl.url,
        "title":        dl.title,
        "channel":      dl.channel,
        "status":       dl.status,
        "download_type":dl.download_type,
        "progress":     dl.progress,
        "speed":        dl.speed,
        "eta":          dl.eta,
        "filesize":     dl.filesize,
        "resolution":   dl.resolution,
        "source_site":  dl.source_site,
        "thumbnail":    dl.thumbnail,
        "file_path":    dl.file_path,
        "subtitle_langs":  dl.subtitle_langs,
        "subtitle_format": dl.subtitle_format,
        "subtitle_auto":   dl.subtitle_auto,
        "embed_subtitles": dl.embed_subtitles,
        "hardsub":         dl.hardsub,
        "container_format": dl.container_format,
        "write_metadata":   dl.write_metadata,
        "playlist_items":   dl.playlist_items,
        "playlist_end":     dl.playlist_end,
        "date_after":       dl.date_after,
        "error_msg":    dl.error_msg,
        "retry_count":  dl.retry_count,
        "priority":     dl.priority,
        "created_at":   dl.created_at.isoformat() if dl.created_at else None,
        "completed_at": dl.completed_at.isoformat() if dl.completed_at else None,
    }
