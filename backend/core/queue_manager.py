"""
Queue Manager — async priority queue for managing download tasks
"""

import asyncio
import logging
from datetime import datetime, timezone
import uuid

from sqlalchemy import select, update, text

from database.db_manager import AsyncSessionLocal
from database.models import Download, DownloadStatus, QueueItem

logger = logging.getLogger("streamvault.queue")


class QueueManager:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False
        self._paused  = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("QueueManager started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def pause(self):
        self._paused = True

    async def resume(self):
        self._paused = False

    async def add(self, download_id: str, priority: int = 5) -> QueueItem:
        async with AsyncSessionLocal() as session:
            # Atomic insert that computes next position using current MAX(position) in a single statement
            new_id = str(uuid.uuid4())
            added_at = datetime.now(timezone.utc)
            await session.execute(
                text(
                    """
                    INSERT INTO queue (id, download_id, position, priority, added_at)
                    SELECT :id, :download_id, COALESCE(MAX(position), -1) + 1, :priority, :added_at FROM queue
                    """
                ),
                {"id": new_id, "download_id": download_id, "priority": priority, "added_at": added_at},
            )
            await session.commit()

            result = await session.execute(select(QueueItem).where(QueueItem.id == new_id))
            item = result.scalar_one()
            return item

    async def remove(self, download_id: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(QueueItem).where(QueueItem.download_id == download_id)
            )
            item = result.scalar_one_or_none()
            if item:
                await session.delete(item)
                await session.commit()

    async def reorder(self, download_id: str, new_position: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(QueueItem).where(QueueItem.download_id == download_id)
            )
            item = result.scalar_one_or_none()
            if item:
                item.position = new_position
                await session.commit()

    async def list_queue(self) -> list[dict]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(QueueItem, Download)
                .join(Download, QueueItem.download_id == Download.id)
                .order_by(QueueItem.priority, QueueItem.position)
            )
            rows = result.all()
        return [
            {
                "queue_id":    q.id,
                "download_id": q.download_id,
                "position":    q.position,
                "priority":    q.priority,
                "added_at":    q.added_at,
                "title":       d.title,
                "url":         d.url,
                "status":      d.status,
                "source_site": d.source_site,
                "resolution":  d.resolution,
                "filesize":    d.filesize,
            }
            for q, d in rows
        ]

    async def clear(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(QueueItem))
            for item in result.scalars().all():
                await session.delete(item)
            await session.commit()

    async def _loop(self):
        from config.config_manager import ConfigManager
        from core.downloader_engine import start_download, _active

        cfg = ConfigManager()

        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                max_concurrent = int(cfg.get("max_concurrent", "4"))
                active_count   = len(_active)

                if active_count >= max_concurrent:
                    await asyncio.sleep(1)
                    continue

                slots = max_concurrent - active_count
                if slots <= 0:
                    await asyncio.sleep(1)
                    continue

                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(QueueItem)
                        .join(Download, QueueItem.download_id == Download.id)
                        .where(Download.status == DownloadStatus.QUEUED)
                        .order_by(QueueItem.priority, QueueItem.position)
                        .limit(slots)
                    )
                    items = result.scalars().all()

                    # ARCH-4: atomically claim each item by flipping its status
                    # here, in the same transaction as the SELECT above,
                    # rather than leaving that to happen later when the
                    # dispatched task actually starts running. Without this,
                    # a narrow window exists between the SELECT and the
                    # task's first `await` (near-immediate under normal load,
                    # not guaranteed under event-loop contention) during which
                    # the same QUEUED item could be selected and dispatched
                    # twice. The rowcount check makes the claim itself the
                    # single point of truth — the UPDATE only matches if the
                    # row is still QUEUED, so a losing race claims nothing.
                    claimed_ids = []
                    for item in items:
                        claim = await session.execute(
                            update(Download)
                            .where(Download.id == item.download_id, Download.status == DownloadStatus.QUEUED)
                            .values(status=DownloadStatus.DOWNLOADING)
                        )
                        if claim.rowcount == 1:
                            claimed_ids.append(item.download_id)
                    await session.commit()

                for download_id in claimed_ids:
                    logger.info(f"Queue: starting {download_id}")
                    asyncio.create_task(start_download(download_id))

                await asyncio.sleep(2)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Queue loop error: {exc}")
                await asyncio.sleep(5)


# Singleton instance shared across the whole app
_instance: QueueManager | None = None

def get_queue_manager() -> QueueManager:
    global _instance
    if _instance is None:
        _instance = QueueManager()
    return _instance
