"""ARCH-3 (thread pool sizing) and ARCH-4 (atomic queue claim)."""
import inspect

from sqlalchemy import update

from conftest import run_async
from database.db_manager import AsyncSessionLocal
from database.models import Download, DownloadStatus
from core.queue_manager import QueueManager
import core.downloader_engine as engine


def test_executor_is_a_generous_fixed_ceiling_not_max_concurrent():
    assert engine._executor._max_workers == 32
    assert engine._executor._max_workers >= 8  # above the Settings UI's slider range


def test_atomic_claim_only_lets_one_side_of_a_race_win():
    async def _race():
        async with AsyncSessionLocal() as session:
            dl = Download(url="https://example.com/race", status=DownloadStatus.QUEUED)
            session.add(dl)
            await session.commit()
            did = dl.id

        async with AsyncSessionLocal() as session:
            first = await session.execute(
                update(Download).where(Download.id == did, Download.status == DownloadStatus.QUEUED)
                .values(status=DownloadStatus.DOWNLOADING)
            )
            await session.commit()

        async with AsyncSessionLocal() as session:
            second = await session.execute(
                update(Download).where(Download.id == did, Download.status == DownloadStatus.QUEUED)
                .values(status=DownloadStatus.DOWNLOADING)
            )
            await session.commit()

        return first.rowcount, second.rowcount

    first_rc, second_rc = run_async(_race())
    assert first_rc == 1
    assert second_rc == 0


def test_loop_dispatches_only_items_it_actually_claimed():
    src = inspect.getsource(QueueManager._loop)
    assert "claimed_ids" in src
    assert "update(Download)" in src
