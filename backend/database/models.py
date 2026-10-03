"""
SQLAlchemy ORM models — supports SQLite (default) and PostgreSQL
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import enum
import uuid

Base = declarative_base()

def _now():
    return datetime.now(timezone.utc)

def _uuid():
    return str(uuid.uuid4())


class DownloadStatus(str, enum.Enum):
    PENDING    = "pending"
    QUEUED     = "queued"
    DOWNLOADING = "downloading"
    PROCESSING  = "processing"
    COMPLETED   = "completed"
    PAUSED     = "paused"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


class DownloadType(str, enum.Enum):
    VIDEO    = "video"
    AUDIO    = "audio"
    PLAYLIST = "playlist"
    CHANNEL  = "channel"
    SUBTITLE = "subtitle"


class Download(Base):
    __tablename__ = "downloads"

    id           = Column(String,  primary_key=True, default=_uuid)
    url          = Column(String,  nullable=False)
    title        = Column(String,  nullable=True)
    channel      = Column(String,  nullable=True)
    duration     = Column(Integer, nullable=True)   # seconds
    view_count   = Column(Integer, nullable=True)
    resolution   = Column(String,  nullable=True)
    fps          = Column(Integer, nullable=True)
    filesize     = Column(Integer, nullable=True)   # bytes
    file_path    = Column(String,  nullable=True)
    thumbnail    = Column(String,  nullable=True)
    source_site  = Column(String,  nullable=True)
    download_type = Column(SAEnum(DownloadType), default=DownloadType.VIDEO)
    status       = Column(SAEnum(DownloadStatus), default=DownloadStatus.PENDING, index=True)
    progress     = Column(Float,   default=0.0)     # 0–100
    speed        = Column(Float,   nullable=True)   # bytes/s
    eta          = Column(Integer, nullable=True)   # seconds
    format_id    = Column(String,  nullable=True)
    quality      = Column(String,  nullable=True)
    audio_format = Column(String,  nullable=True)
    subtitles    = Column(Boolean, default=False)
    subtitle_langs  = Column(String,  nullable=True)   # comma-separated codes, e.g. "en,fr"
    subtitle_format = Column(String,  nullable=True)   # srt/vtt/ass/lrc
    subtitle_auto   = Column(Boolean, default=False)   # include auto-generated captions
    embed_subtitles = Column(Boolean, nullable=True)   # None = use global config default
    hardsub         = Column(Boolean, default=False)   # burn subtitles into the video (re-encode)
    thumbnail_dl = Column(Boolean, default=False)
    output_folder = Column(String, nullable=True)
    container_format = Column(String, nullable=True)   # mp4/mkv/webm — overrides merge_output_format
    write_metadata = Column(Boolean, nullable=True)     # None = use global config default
    playlist_items = Column(String, nullable=True)      # yt-dlp playlist_items spec, e.g. "1-50" or "1,3,5-9"
    playlist_end   = Column(Integer, nullable=True)      # cap on number of items (channel/playlist "Max Videos")
    date_after     = Column(String, nullable=True)       # yt-dlp dateafter spec, e.g. "20240101"
    error_msg    = Column(Text,    nullable=True)
    retry_count  = Column(Integer, default=0)
    priority     = Column(Integer, default=5)       # 1 = highest
    playlist_id  = Column(String,  nullable=True)
    playlist_index = Column(Integer, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now)
    started_at   = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class QueueItem(Base):
    __tablename__ = "queue"

    id          = Column(String,  primary_key=True, default=_uuid)
    download_id = Column(String,  nullable=False, index=True)
    position    = Column(Integer, default=0)
    priority    = Column(Integer, default=5)
    added_at    = Column(DateTime(timezone=True), default=_now)


class Setting(Base):
    __tablename__ = "settings"

    key         = Column(String, primary_key=True)
    value       = Column(Text,   nullable=True)
    description = Column(Text,   nullable=True)
    updated_at  = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class LogEntry(Base):
    __tablename__ = "logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    level       = Column(String,  default="INFO", index=True)
    message     = Column(Text,    nullable=False)
    download_id = Column(String,  nullable=True, index=True)
    created_at  = Column(DateTime(timezone=True), default=_now, index=True)
