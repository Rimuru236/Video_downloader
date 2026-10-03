"""Download lifecycle: REL-1 (resume/retry idempotency), REL-2 (invalid
status query), REL-3 (delete_files + file serving), REL-4 (disk-full
fast-fail), FE-2 (GET .../file)."""
import errno
import os

import pytest

from conftest import run_async
from database.db_manager import AsyncSessionLocal
from database.models import Download, DownloadStatus
import core.downloader_engine as engine


def _make_download(status, file_path=None):
    async def _create():
        async with AsyncSessionLocal() as session:
            dl = Download(url="https://example.com/x", status=status, file_path=file_path)
            session.add(dl)
            await session.commit()
            return dl.id
    return run_async(_create())


def _get(download_id):
    async def _fetch():
        async with AsyncSessionLocal() as session:
            return await session.get(Download, download_id)
    return run_async(_fetch())


# ── REL-2 ────────────────────────────────────────────────────────────────

def test_invalid_status_query_param_is_a_clean_400(client):
    r = client.get("/api/v1/downloads?status=not-a-real-status")
    assert r.status_code == 400
    assert "not-a-real-status" in r.text


def test_valid_status_query_param_still_works(client):
    assert client.get("/api/v1/downloads?status=failed").status_code == 200


# ── REL-1 ────────────────────────────────────────────────────────────────

def test_resume_rejects_duplicate_start_while_active(client):
    did = _make_download(DownloadStatus.PAUSED)

    class _FakeTask:
        def cancel(self): pass

    engine._active[did] = _FakeTask()
    try:
        assert client.post(f"/api/v1/download/{did}/resume").status_code == 409
        assert client.post(f"/api/v1/download/{did}/retry").status_code == 409
    finally:
        engine._active.pop(did, None)


# ── REL-3 / FE-2 ─────────────────────────────────────────────────────────

def test_delete_without_delete_files_leaves_file_on_disk(client, tmp_dir):
    fpath = os.path.join(tmp_dir, "rel3_a.mp4")
    with open(fpath, "w") as f:
        f.write("video")
    did = _make_download(DownloadStatus.COMPLETED, fpath)

    r = client.delete(f"/api/v1/download/{did}")
    assert r.json()["file_deleted"] is False
    assert os.path.exists(fpath)
    os.remove(fpath)


def test_delete_with_delete_files_removes_it(client, tmp_dir):
    fpath = os.path.join(tmp_dir, "rel3_b.mp4")
    with open(fpath, "w") as f:
        f.write("video")
    did = _make_download(DownloadStatus.COMPLETED, fpath)

    r = client.delete(f"/api/v1/download/{did}?delete_files=true")
    assert r.json()["file_deleted"] is True
    assert not os.path.exists(fpath)


def test_get_file_serves_existing_file(client, tmp_dir):
    fpath = os.path.join(tmp_dir, "fe2.mp4")
    with open(fpath, "wb") as f:
        f.write(b"fake mp4 bytes")
    did = _make_download(DownloadStatus.COMPLETED, fpath)

    r = client.get(f"/api/v1/download/{did}/file")
    assert r.status_code == 200
    assert r.content == b"fake mp4 bytes"


def test_get_file_404s_when_no_file_path(client):
    did = _make_download(DownloadStatus.DOWNLOADING, None)
    assert client.get(f"/api/v1/download/{did}/file").status_code == 404


def test_get_file_404s_when_path_set_but_missing_on_disk(client, tmp_dir):
    fpath = os.path.join(tmp_dir, "gone.mp4")
    did = _make_download(DownloadStatus.COMPLETED, fpath)  # never actually created
    assert client.get(f"/api/v1/download/{did}/file").status_code == 404


# ── REL-4 ────────────────────────────────────────────────────────────────

def test_disk_full_fails_immediately_without_retrying():
    did = _make_download(DownloadStatus.PENDING)

    def _raise_enospc(*a, **k):
        raise OSError(errno.ENOSPC, "No space left on device")

    orig = engine._run_ydl
    engine._run_ydl = _raise_enospc
    try:
        run_async(engine._download_task(did, None))
    finally:
        engine._run_ydl = orig

    dl = _get(did)
    assert dl.status == DownloadStatus.FAILED
    assert "disk full" in dl.error_msg.lower()
    assert dl.retry_count == 0
