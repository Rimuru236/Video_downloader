"""
Downloader Engine — yt-dlp wrapper with progress tracking, retry logic,
FFmpeg post-processing, and WebSocket progress broadcasting.
"""

import asyncio
import errno
import logging
import os
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional

import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import PostProcessingError
from sqlalchemy.ext.asyncio import AsyncSession

from config.config_manager import ConfigManager
from database.db_manager import AsyncSessionLocal
from database.models import Download, DownloadStatus
from utils.db_logger import log_event
from utils.url_validator import validate_url

logger = logging.getLogger("streamvault.engine")
config  = ConfigManager()

# ARCH-3: this used to be sized directly from max_concurrent, read once at
# import time — raising "Concurrent Downloads" in Settings above whatever
# the process started with had no real effect, since the pool itself
# couldn't grow past its original size (lowering it worked fine; the queue
# loop just used fewer of the available threads). Recreating a
# ThreadPoolExecutor at runtime is its own can of worms (draining in-flight
# futures safely, swapping the module-level reference without a race), so
# instead: size this as a generous fixed ceiling, decoupled from
# max_concurrent entirely, and let QueueManager's active-task-count check
# (comparing against max_concurrent) be the *sole* concurrency gate — I/O-
# bound work like this tolerates a much larger pool than the CPU count would
# suggest, so a high ceiling costs little. executor_max_workers is an
# advanced/rarely-tuned escape hatch for anyone who legitimately wants
# max_concurrent set higher than the default ceiling.
_executor = ThreadPoolExecutor(max_workers=int(config.get("executor_max_workers", "32")))

# Registry of active download tasks: download_id -> asyncio.Task
_active: dict[str, asyncio.Task] = {}
# Registry of progress callbacks for WebSocket push
_progress_hooks: dict[str, list[Callable]] = {}
# Progress update throttling: download_id -> last_update_time
_progress_last_update: dict[str, float] = {}
# Cancellation events for downloads (thread-safe)
_cancel_events: dict[str, threading.Event] = {}
# Throttle interval for progress updates (seconds) - configurable
_PROGRESS_THROTTLE_SECONDS = float(config.get("progress_throttle", "2"))
# REL-3: final on-disk path of a completed download, captured via a
# postprocessor hook (see _make_postprocessor_hook) so DELETE ?delete_files=
# has something to actually delete. Written from the executor thread, read
# from the event loop after run_in_executor's await returns — that await is
# a happens-before edge, so a plain dict is safe here without extra locking.
_final_filepaths: dict[str, str] = {}


def register_progress_hook(download_id: str, fn: Callable):
    _progress_hooks.setdefault(download_id, []).append(fn)


def unregister_progress_hook(download_id: str):
    _progress_hooks.pop(download_id, None)


def _make_postprocessor_hook(download_id: str):
    """Captures the truly-final file path — postprocessors run in sequence
    (extract-audio, embed-subtitle, hardsub, ...) and each may rename/replace
    the file, so only the *last* 'finished' event holds the actual result."""
    def hook(d: dict):
        if d.get("status") == "finished":
            info = d.get("info_dict") or {}
            fp = info.get("filepath")
            if fp:
                _final_filepaths[download_id] = fp
    return hook


# ──────────────────────────────────────────────
# Internal yt-dlp helpers
# ──────────────────────────────────────────────

class _HardsubPostProcessor(PostProcessor):
    """Burns the first requested subtitle track directly into the video
    frame via ffmpeg's `subtitles` filter (a permanent re-encode), as
    opposed to FFmpegEmbedSubtitle's soft/switchable muxed track.

    Registered at the 'post_process' stage (after yt-dlp's built-in
    FFmpegSubtitlesConvertor, so the subtitle file is already in its final
    requested format) and BEFORE yt-dlp's file-move step, so both the video
    and subtitle files are still sitting side-by-side in the working
    directory — no need to guess at post-move destination paths.
    """

    def run(self, info):
        filepath = info.get("filepath")
        subs = info.get("requested_subtitles") or {}
        if not filepath or not os.path.exists(filepath) or not subs:
            self.report_warning("Hardsub requested but no subtitle/video file available — skipping burn-in")
            return [], info

        # First requested language, in the order the user asked for them.
        sub_info = next(iter(subs.values()))
        sub_path = sub_info.get("filepath")
        if not sub_path or not os.path.exists(sub_path):
            self.report_warning("Hardsub requested but the subtitle file is missing — skipping burn-in")
            return [], info

        base, ext = os.path.splitext(filepath)
        out_path = f"{base}.hardsub.tmp{ext}"

        # ffmpeg's `subtitles` filter treats ':' and other characters specially
        # inside the filtergraph string — escape so Windows drive letters survive.
        escaped_sub = sub_path.replace("\\", "/").replace(":", r"\:")

        cmd = [
            "ffmpeg", "-y", "-i", filepath,
            "-vf", f"subtitles='{escaped_sub}'",
            "-c:a", "copy",
            out_path,
        ]
        # ffmpeg writes UTF-8 to stderr regardless of platform locale; forcing
        # the OS default (cp1252 on Windows) here crashes the subprocess
        # module's background stderr-reader thread on any non-ASCII byte.
        #
        # SEC-7: this is a real transcode, not a quick check, so the timeout
        # needs to be generous and configurable rather than a short fixed
        # value — but it still needs one, since a hung ffmpeg process on a
        # corrupt input would otherwise tie up a thread-pool worker forever,
        # with no way for the pool to reclaim it.
        try:
            ffmpeg_timeout = int(config.get("ffmpeg_timeout", "3600"))
        except ValueError:
            ffmpeg_timeout = 3600
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=ffmpeg_timeout,
            )
        except subprocess.TimeoutExpired:
            raise PostProcessingError(f"Hardsub burn-in timed out after {ffmpeg_timeout}s")
        if result.returncode != 0 or not os.path.exists(out_path):
            raise PostProcessingError(f"Hardsub burn-in failed: {result.stderr[-800:]}")

        os.replace(out_path, filepath)
        self.to_screen(f"Burned subtitles into {filepath}")
        return [], info


def _build_ydl_opts(download: Download, output_folder: str, socket_timeout: int, deno_path: str = "") -> dict:
    quality   = download.quality or config.get("default_quality", "bestvideo[vcodec^=avc1]+bestaudio/bestvideo[ext=mp4]+bestaudio/best")
    cookies   = config.get("cookies_file", "")
    proxy     = config.get("proxy", "")
    rate      = int(config.get("rate_limit", "0"))
    use_aria2 = config.get("use_aria2", "false").lower() == "true"

    subtitle_only = download.download_type.value == "subtitle"
    want_subtitles = download.subtitles or subtitle_only
    hardsub = bool(download.hardsub)
    embed_subs = (
        download.embed_subtitles if download.embed_subtitles is not None
        else config.get("embed_subtitles", "false") == "true"
    )
    # Subtitle-only requests skip the media entirely UNLESS the user asked to
    # embed (soft) or burn in (hard) the subtitles — both need the video.
    skip_download = subtitle_only and not embed_subs and not hardsub

    subtitle_langs = [
        l.strip() for l in (download.subtitle_langs or config.get("subtitle_lang", "en")).split(",")
        if l.strip()
    ]
    # Hardsub burns in via ffmpeg's `subtitles` filter, which needs a file
    # format it can parse reliably — fall back to srt if none was requested.
    subtitle_format = download.subtitle_format or ("srt" if hardsub else None)

    outtmpl = os.path.join(output_folder, "%(title)s.%(ext)s")

    # Determine postprocessors. For audio-only downloads, use configured audio_format by default.
    postprocessors = []
    audio_codec = None
    if download.audio_format:
        audio_codec = download.audio_format
    elif download.download_type.value == "audio":
        audio_codec = config.get("audio_format", None)

    if audio_codec and not skip_download:
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_codec,
            "preferredquality": "192",
        })
    # Embedding subtitles into the media file makes no sense when the media
    # itself isn't being downloaded. Hardsub takes precedence over the soft
    # embed — burning in already bakes the subtitles into the frame, so a
    # separate switchable track would be redundant.
    if want_subtitles and embed_subs and not hardsub and not skip_download:
        postprocessors.append({"key": "FFmpegEmbedSubtitle"})
    # Convert fetched subtitles to the requested format (e.g. vtt -> srt) —
    # must run before the hardsub burn-in postprocessor, which is appended
    # separately in _run_ydl() after the YoutubeDL instance exists.
    if want_subtitles and subtitle_format:
        postprocessors.append({"key": "FFmpegSubtitlesConvertor", "format": subtitle_format})
    write_metadata = (
        download.write_metadata if download.write_metadata is not None
        else config.get("write_metadata", "true") == "true"
    )
    if write_metadata and not skip_download:
        postprocessors.append({"key": "FFmpegMetadata"})

    opts = {
        "format":          quality,
        "outtmpl":         outtmpl,
        "writethumbnail":  download.thumbnail_dl or (config.get("write_thumbnail", "false") == "true"),
        "writesubtitles":  want_subtitles,
        "writeautomaticsub": want_subtitles and bool(download.subtitle_auto),
        "subtitleslangs":  subtitle_langs,
        # Subtitle-only download_type: fetch subtitles/thumbnail/metadata but
        # skip downloading the actual media (yt-dlp's skip_download) — unless
        # embedding or hardsub was requested, which need the media present.
        "skip_download":   skip_download,
        "postprocessors":  postprocessors,
        # Not a real yt-dlp option — read and popped by _run_ydl() to decide
        # whether to attach the custom _HardsubPostProcessor instance.
        "_hardsub":        want_subtitles and hardsub and not skip_download,
        # noplaylist: treat both playlist and channel as multi-item sources
        "noplaylist":      download.download_type.value not in ("playlist", "channel"),
        "retries":         int(config.get("max_retries", "5")),
        "fragment_retries": 5,
        "continuedl":      True,
        "ignoreerrors":    False,
        "quiet":           True,
        "no_warnings":     True,
        "socket_timeout":  socket_timeout,
        # REL-3: capture the true final on-disk path (after any postprocessor
        # renames it) so DELETE /download/{id}?delete_files=true has
        # something to actually clean up.
        "postprocessor_hooks": [_make_postprocessor_hook(download.id)],
    }

    # Configure Deno JavaScript runtime for yt-dlp EJS support
    # If deno_path is configured, use it; otherwise let yt-dlp auto-detect from PATH
    js_runtimes = {}
    if deno_path:
        js_runtimes["deno"] = {"path": deno_path}
    else:
        js_runtimes["deno"] = {}
    opts["js_runtimes"] = js_runtimes
    # Only set merge_output_format when format implies video+audio merging.
    # container_format lets a caller request mkv/webm instead of the mp4
    # default (e.g. the "Container" picker in the Add Download modal).
    if not skip_download and (("+" in (quality or "")) or ("bestvideo" in (quality or ""))):
        opts["merge_output_format"] = download.container_format or "mp4"

    # Playlist/channel item selection & filtering — only meaningful for
    # multi-item sources, but harmless to set regardless since yt-dlp ignores
    # them for single-video downloads.
    if download.playlist_items:
        opts["playlist_items"] = download.playlist_items
    if download.playlist_end:
        opts["playlistend"] = download.playlist_end
    if download.date_after:
        from yt_dlp.utils import DateRange
        opts["daterange"] = DateRange(download.date_after)

    if cookies:
        opts["cookiefile"] = cookies
    if proxy:
        opts["proxy"] = proxy
    if rate > 0:
        opts["ratelimit"] = rate * 1024
    if use_aria2:
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = ["--min-split-size=1M", "--max-connection-per-server=4"]
    return opts


def _make_progress_hook(download_id: str, loop: asyncio.AbstractEventLoop):
    def hook(d: dict):
        # If user requested cancellation, raise to abort yt-dlp
        evt = _cancel_events.get(download_id)
        if evt and evt.is_set():
            raise Exception("Cancelled by user")

        status = d.get("status")
        if status == "downloading":
            total   = d.get("total_bytes") or d.get("total_bytes_estimate")
            dled    = d.get("downloaded_bytes", 0)
            speed   = d.get("speed") or 0
            eta     = d.get("eta") or 0

            # Only calculate percentage when total is known and non-zero
            pct = None
            if total and total > 0:
                pct = round((dled / total) * 100, 1)

            payload = {
                "download_id": download_id,
                "progress":    pct,
                "speed":       speed,
                "eta":         eta,
                "filesize":    total,
                "downloaded":  dled,
            }
            # Push to WebSocket hooks (immediate for UI responsiveness)
            for fn in _progress_hooks.get(download_id, []):
                asyncio.run_coroutine_threadsafe(fn(payload), loop)

            # Persist progress to DB (throttled to every 2 seconds) — only persist pct when available
            current_time = time.time()
            last_update = _progress_last_update.get(download_id, 0)
            if current_time - last_update >= _PROGRESS_THROTTLE_SECONDS:
                _progress_last_update[download_id] = current_time
                if pct is not None:
                    asyncio.run_coroutine_threadsafe(
                        _update_progress(download_id, pct, speed, eta, total), loop
                    )
                else:
                    # Persist speed/eta/filesize/downloaded for UI even without pct
                    asyncio.run_coroutine_threadsafe(
                        _update_progress(download_id, None, speed, eta, total), loop
                    )

        elif status == "finished":
            logger.info(f"[{download_id}] Download finished, post-processing…")
            # Clear throttling state on completion
            _progress_last_update.pop(download_id, None)

    return hook


# REL-6: _update_progress() intentionally swallows every exception at debug
# level — the right call for not crashing a download over one flaky
# progress write — but with nothing counting them, a systemic DB issue
# during a long download would go completely unnoticed. Tracked here,
# exposed via /metrics (see routes_metrics.py), and escalated to a WARNING
# every _PROGRESS_FAILURE_WARN_EVERY failures so a real problem still
# surfaces in the logs without one-WARNING-per-progress-tick spam.
_progress_persist_failures = 0
_PROGRESS_FAILURE_WARN_EVERY = 10


def progress_persist_failure_count() -> int:
    """OBS-3: cumulative count of failed progress DB writes, for /metrics."""
    return _progress_persist_failures


async def _update_progress(
    download_id: str,
    progress: float,
    speed: float,
    eta: int,
    filesize: int,
):
    global _progress_persist_failures
    try:
        async with AsyncSessionLocal() as session:
            dl = await session.get(Download, download_id)
            if dl:
                dl.progress = progress
                dl.speed    = speed
                dl.eta      = eta
                dl.filesize = filesize
                await session.commit()
    except Exception as exc:
        _progress_persist_failures += 1
        logger.debug(f"Progress DB update error: {exc}")
        if _progress_persist_failures % _PROGRESS_FAILURE_WARN_EVERY == 0:
            logger.warning(
                f"Progress persistence has failed {_progress_persist_failures} times total "
                f"— possible systemic DB issue (most recent: {exc})"
            )


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def active_count() -> int:
    """OBS-3: number of downloads currently running in this process — used
    by the /metrics endpoint."""
    return len(_active)


def is_active(download_id: str) -> bool:
    """REL-1: whether a download already has a running task in this process.
    Callers (resume/retry) use this to reject a duplicate start instead of
    launching a second concurrent yt-dlp process against the same output
    file."""
    return download_id in _active


async def start_download(download_id: str):
    """Kick off a download in the thread pool."""
    # Create a cancellation event immediately so callers can cancel before the worker starts
    _cancel_events[download_id] = threading.Event()
    loop = asyncio.get_event_loop()
    task = asyncio.create_task(_download_task(download_id, loop))
    _active[download_id] = task
    def _done_callback(_):
        _active.pop(download_id, None)
        # Clean up cancel event
        _cancel_events.pop(download_id, None)
    task.add_done_callback(_done_callback)
    return task


async def cancel_download(download_id: str, _log: bool = True):
    # Signal the worker via event to abort (safe for blocking yt-dlp runs)
    evt = _cancel_events.get(download_id)
    if evt:
        evt.set()
    task = _active.get(download_id)
    if task:
        task.cancel()
    async with AsyncSessionLocal() as session:
        dl = await session.get(Download, download_id)
        if dl:
            dl.status = DownloadStatus.CANCELLED
            await session.commit()
    if _log:
        await log_event("WARN", "Download cancelled by user", download_id)


async def pause_download(download_id: str):
    """Mark as paused — actual yt-dlp pause isn't native; cancel and mark for resume."""
    # _log=False: cancel_download() is being used here as an internal
    # implementation detail of pausing, not a user-initiated cancel — the
    # "Download paused" entry logged below is the one that should show up.
    await cancel_download(download_id, _log=False)
    async with AsyncSessionLocal() as session:
        dl = await session.get(Download, download_id)
        if dl:
            dl.status = DownloadStatus.PAUSED
            await session.commit()
    await log_event("INFO", "Download paused", download_id)


async def _download_task(download_id: str, loop: asyncio.AbstractEventLoop):
    # Use async config reads so database-persisted settings take effect
    max_retries = int(await config.get_async("max_retries", "5"))
    backoff_base = float(await config.get_async("retry_backoff", "2"))
    deno_path = await config.get_async("deno_path", "")

    for attempt in range(max_retries + 1):
        try:
            async with AsyncSessionLocal() as session:
                dl = await session.get(Download, download_id)
                if dl is None:
                    logger.error(f"Download {download_id} not found in DB")
                    return
                dl.status     = DownloadStatus.DOWNLOADING
                dl.started_at = datetime.now(timezone.utc)
                dl.retry_count = attempt
                await session.commit()
                url           = dl.url
                output_folder = dl.output_folder or await config.get_async("download_folder", "./downloads")
                try:
                    socket_timeout = int(await config.get_async("socket_timeout", "15"))
                except Exception:
                    socket_timeout = 15
                opts          = _build_ydl_opts(dl, output_folder, socket_timeout, deno_path)

            if attempt == 0:
                await log_event("INFO", f"Download started: {url}", download_id)

            opts["progress_hooks"] = [_make_progress_hook(download_id, loop)]
            os.makedirs(output_folder, exist_ok=True)

            # SEC-3: validate_url() already ran once at submission time, but a
            # download can sit queued for a while (and retries wait even
            # longer via backoff) before actually reaching this point — DNS
            # can change in that window. Re-checking right before the fetch
            # shrinks that gap from "however long the queue/backoff takes" to
            # milliseconds. It does not (and cannot, from here) protect
            # against a redirect yt-dlp follows internally after this check —
            # see the README's "Known limitations" section.
            is_valid, reason = validate_url(url)
            if not is_valid:
                logger.error(f"[{download_id}] Pre-fetch re-validation failed: {reason}")
                async with AsyncSessionLocal() as session:
                    dl = await session.get(Download, download_id)
                    if dl:
                        dl.status    = DownloadStatus.FAILED
                        dl.error_msg = f"URL failed pre-fetch validation: {reason}"
                        await session.commit()
                await log_event("ERROR", f"Download blocked at fetch time: {reason}", download_id)
                return  # do not retry — a failing revalidation should not be retried

            await asyncio.get_event_loop().run_in_executor(
                _executor, _run_ydl, url, opts
            )

            async with AsyncSessionLocal() as session:
                dl = await session.get(Download, download_id)
                if dl:
                    dl.status       = DownloadStatus.COMPLETED
                    dl.progress     = 100.0
                    dl.completed_at = datetime.now(timezone.utc)
                    dl.file_path    = _final_filepaths.pop(download_id, None)
                    await session.commit()
                    title = dl.title or url
            logger.info(f"[{download_id}] Completed successfully")
            await log_event("OK", f"Download completed: {title}", download_id)
            return

        except asyncio.CancelledError:
            logger.info(f"[{download_id}] Cancelled")
            _final_filepaths.pop(download_id, None)
            # Ensure DB marked cancelled
            async with AsyncSessionLocal() as session:
                dl = await session.get(Download, download_id)
                if dl:
                    dl.status = DownloadStatus.CANCELLED
                    await session.commit()
            return

        except Exception as exc:
            # If exception came from user cancellation via progress hook, treat as cancelled
            if "cancel" in str(exc).lower():
                logger.info(f"[{download_id}] Aborted: {exc}")
                _final_filepaths.pop(download_id, None)
                async with AsyncSessionLocal() as session:
                    dl = await session.get(Download, download_id)
                    if dl:
                        dl.status = DownloadStatus.CANCELLED
                        await session.commit()
                return

            # REL-4: a full disk will fail identically on every retry — burning
            # through max_retries with growing backoff delays before failing
            # only delays the inevitable and does nothing to fix it. errno 28
            # (ENOSPC) is the POSIX "No space left on device" code; Windows
            # raises OSError with winerror 112 for the same condition.
            is_disk_full = isinstance(exc, OSError) and (
                getattr(exc, "errno", None) == errno.ENOSPC or getattr(exc, "winerror", None) == 112
            )
            if is_disk_full:
                logger.error(f"[{download_id}] Disk full — failing immediately without retry: {exc}")
                _final_filepaths.pop(download_id, None)
                async with AsyncSessionLocal() as session:
                    dl = await session.get(Download, download_id)
                    if dl:
                        dl.status    = DownloadStatus.FAILED
                        dl.error_msg = f"Disk full: {exc}"
                        await session.commit()
                await log_event("ERROR", f"Download failed — disk full: {exc}", download_id)
                return

            logger.warning(f"[{download_id}] Attempt {attempt+1} failed: {exc}")
            if attempt < max_retries:
                wait = backoff_base ** attempt
                logger.info(f"[{download_id}] Retry in {wait:.0f}s…")
                await log_event("WARN", f"Attempt {attempt+1} failed: {exc} — retrying in {wait:.0f}s", download_id)
                await asyncio.sleep(wait)
            else:
                _final_filepaths.pop(download_id, None)
                async with AsyncSessionLocal() as session:
                    dl = await session.get(Download, download_id)
                    if dl:
                        dl.status    = DownloadStatus.FAILED
                        dl.error_msg = str(exc)
                        await session.commit()
                logger.error(f"[{download_id}] All retries exhausted: {exc}")
                await log_event("ERROR", f"Download failed after {max_retries + 1} attempts: {exc}", download_id)


def _run_ydl(url: str, opts: dict):
    """Run yt-dlp synchronously inside the thread pool."""
    opts = dict(opts)
    hardsub = opts.pop("_hardsub", False)
    with yt_dlp.YoutubeDL(opts) as ydl:
        if hardsub:
            # Registered after the dict-based postprocessors (which default
            # to the same 'post_process' stage) are already attached, so this
            # runs last within that stage — after subtitle format conversion,
            # before yt-dlp moves files to their final destination.
            ydl.add_post_processor(_HardsubPostProcessor(), when="post_process")
        ydl.download([url])


def shutdown_executors():
    """Clean shutdown of thread pool executor."""
    global _executor
    if _executor:
        logger.info("Shutting down downloader engine executor...")
        _executor.shutdown(wait=True)
        _executor = None
