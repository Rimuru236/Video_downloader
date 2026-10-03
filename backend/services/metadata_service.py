"""
Metadata Service — extract rich info from URLs using yt-dlp without downloading
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import yt_dlp

from config.config_manager import ConfigManager

logger  = logging.getLogger("streamvault.metadata")
config  = ConfigManager()
_pool   = ThreadPoolExecutor(max_workers=4)

# Simple in-memory cache with TTL
_metadata_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = float(config.get("metadata_cache_ttl", "300"))  # Configurable
_CACHE_MAX_SIZE = int(config.get("metadata_cache_size", "1000"))  # Configurable


async def extract_metadata(url: str) -> dict:
    # Check cache first
    current_time = time.time()
    cached = _metadata_cache.get(url)
    if cached and (current_time - cached[0]) < _CACHE_TTL_SECONDS:
        logger.debug(f"Cache hit for {url}")
        return cached[1]
    
    # Cache miss or expired, fetch fresh data
    loop = asyncio.get_event_loop()
    # Respect configured socket timeout (may be persisted in DB)
    try:
        timeout = int(await config.get_async("socket_timeout", "15"))
    except Exception:
        timeout = 15
    result = await loop.run_in_executor(_pool, _fetch, url, timeout)
    
    # Update cache
    _metadata_cache[url] = (current_time, result)
    
    # Clean up old cache entries periodically
    if len(_metadata_cache) > _CACHE_MAX_SIZE:  # Prevent unbounded growth
        _cleanup_cache()
    
    return result


def _cleanup_cache():
    """Remove expired entries from cache."""
    current_time = time.time()
    expired_keys = [
        url for url, (timestamp, _) in _metadata_cache.items()
        if (current_time - timestamp) >= _CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        del _metadata_cache[key]
    logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def _fetch(url: str, socket_timeout: int) -> dict:
    opts = {
        "quiet":           True,
        "no_warnings":     True,
        "extract_flat":    False,
        "skip_download":   True,
        "forcejson":       False,
        "socket_timeout":  socket_timeout,
    }
    cookies = config.get("cookies_file", "")
    proxy   = config.get("proxy", "")
    if cookies:
        opts["cookiefile"] = cookies
    if proxy:
        opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError("Could not extract metadata from URL")

    entries = info.get("entries")  # playlist / channel
    if entries:
        entries = list(entries)
        return {
            "type":        "playlist",
            "id":          info.get("id"),
            "title":       info.get("title"),
            "uploader":    info.get("uploader") or info.get("channel"),
            "url":         url,
            "entry_count": len(entries),
            "entries": [
                {
                    "id":        e.get("id"),
                    "title":     e.get("title"),
                    "url":       e.get("webpage_url") or e.get("url"),
                    "duration":  e.get("duration"),
                    "thumbnail": e.get("thumbnail"),
                }
                for e in entries[:100]   # cap at 100 for preview
            ],
        }

    formats = []
    for f in (info.get("formats") or []):
        if f.get("vcodec") != "none" or f.get("acodec") != "none":
            formats.append({
                "format_id":  f.get("format_id"),
                "ext":        f.get("ext"),
                "resolution": f.get("resolution"),
                "fps":        f.get("fps"),
                "vcodec":     f.get("vcodec"),
                "acodec":     f.get("acodec"),
                "filesize":   f.get("filesize") or f.get("filesize_approx"),
                "tbr":        f.get("tbr"),
            })

    subtitles = {}
    for lang, subs in (info.get("subtitles") or {}).items():
        subtitles[lang] = [s.get("ext") for s in subs]
    for lang, subs in (info.get("automatic_captions") or {}).items():
        subtitles.setdefault(f"{lang} (auto)", [s.get("ext") for s in subs])

    return {
        "type":        "video",
        "id":          info.get("id"),
        "title":       info.get("title"),
        "description": (info.get("description") or "")[:500],
        "uploader":    info.get("uploader"),
        "channel":     info.get("channel"),
        "channel_url": info.get("channel_url"),
        "upload_date": info.get("upload_date"),
        "duration":    info.get("duration"),
        "view_count":  info.get("view_count"),
        "like_count":  info.get("like_count"),
        "thumbnail":   info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or url,
        "extractor":   info.get("extractor_key"),
        "formats":     formats,
        "subtitles":   subtitles,
    }


def _fetch_flat_entries(url: str, socket_timeout: int, limit: Optional[int]) -> dict:
    """Fast, shallow extraction of a playlist/channel's entries — used for
    batch operations (e.g. queuing subtitle jobs per video) where we need the
    full member list, not just a capped preview, and don't want yt-dlp to
    eagerly resolve every video's full metadata (slow for large channels)."""
    opts = {
        "quiet":         True,
        "no_warnings":   True,
        "extract_flat":  "in_playlist",
        "skip_download": True,
        "socket_timeout": socket_timeout,
    }
    cookies = config.get("cookies_file", "")
    proxy   = config.get("proxy", "")
    if cookies:
        opts["cookiefile"] = cookies
    if proxy:
        opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError("Could not extract metadata from URL")

    entries = list(info.get("entries") or [])
    if limit:
        entries = entries[:limit]

    return {
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "entry_count_total": len(info.get("entries") or []),
        "entries": [
            {
                "id":    e.get("id"),
                "title": e.get("title"),
                "url":   e.get("url") or e.get("webpage_url"),
            }
            for e in entries if e.get("url") or e.get("webpage_url")
        ],
    }


async def extract_playlist_entries(url: str, limit: Optional[int] = None) -> dict:
    """Uncapped (or `limit`-capped) playlist/channel entry listing for batch jobs."""
    loop = asyncio.get_event_loop()
    try:
        timeout = int(await config.get_async("socket_timeout", "15"))
    except Exception:
        timeout = 15
    return await loop.run_in_executor(_pool, _fetch_flat_entries, url, timeout, limit)


def shutdown_executor():
    """Clean shutdown of metadata service thread pool."""
    global _pool
    if _pool:
        logger.info("Shutting down metadata service executor...")
        _pool.shutdown(wait=True)
        _pool = None
