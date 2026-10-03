"""OBS-2 (request IDs + consistent error shape), OBS-3 (Prometheus metrics),
DATA-2 (log retention pruning), REL-6 (progress-persist failure counter)."""
import re
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from conftest import run_async
from database.db_manager import AsyncSessionLocal
from database.models import Download, DownloadStatus, LogEntry
from core.log_retention import prune_logs
import core.downloader_engine as engine


# ── OBS-2 ────────────────────────────────────────────────────────────────

def test_request_id_header_on_success(client):
    r = client.get("/health")
    assert "x-request-id" in {k.lower() for k in r.headers}


def test_handled_http_exception_has_consistent_shape(client):
    r = client.get("/api/v1/download/does-not-exist")
    body = r.json()
    assert "detail" in body
    assert body.get("request_id")
    assert body["request_id"] == r.headers.get("x-request-id")


def test_unhandled_exception_returns_clean_500(app):
    @app.get("/__test_boom_pytest")
    async def _boom():
        raise RuntimeError("boom")

    noraise_client = TestClient(app, raise_server_exceptions=False)
    r = noraise_client.get("/__test_boom_pytest")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal Server Error"
    assert body.get("request_id")
    assert "boom" not in r.text  # doesn't leak the raw exception to the client


# ── OBS-3 ────────────────────────────────────────────────────────────────

def test_metrics_endpoint_exposes_prometheus_format(client):
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    body = r.text
    for name in (
        "streamvault_downloads_total", "streamvault_queue_depth",
        "streamvault_active_downloads", "streamvault_download_success_rate_percent",
        "streamvault_download_speed_bytes_avg", "streamvault_disk_free_bytes",
    ):
        assert f"# TYPE {name} gauge" in body, f"missing metric: {name}"


def test_queue_depth_reflects_newly_queued_downloads(client):
    def _queue_depth(text):
        m = re.search(r"^streamvault_queue_depth (\d+)$", text, re.MULTILINE)
        return int(m.group(1))

    before = _queue_depth(client.get("/api/v1/metrics").text)

    async def _add():
        async with AsyncSessionLocal() as session:
            session.add(Download(url="https://x/metrics-probe", status=DownloadStatus.QUEUED))
            await session.commit()
    run_async(_add())

    after = _queue_depth(client.get("/api/v1/metrics").text)
    assert after == before + 1


# ── DATA-2 ───────────────────────────────────────────────────────────────

def test_log_retention_prunes_by_age_and_count(client, cfg):
    client.delete("/api/v1/logs")  # clean slate — other tests write logs too

    async def _seed():
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            for i in range(5):
                session.add(LogEntry(level="INFO", message=f"old-{i}", created_at=now - timedelta(days=60)))
            for i in range(5):
                session.add(LogEntry(level="INFO", message=f"recent-{i}", created_at=now - timedelta(days=1)))
            await session.commit()
    run_async(_seed())

    async def _count():
        async with AsyncSessionLocal() as session:
            return (await session.execute(select(func.count(LogEntry.id)))).scalar_one()

    cfg.set("log_retention_days", "30")
    cfg.set("log_retention_max_rows", "0")
    deleted = run_async(prune_logs())
    assert deleted == 5
    assert run_async(_count()) == 5

    cfg.set("log_retention_days", "0")
    cfg.set("log_retention_max_rows", "2")
    deleted2 = run_async(prune_logs())
    assert deleted2 == 3
    assert run_async(_count()) == 2

    cfg.set("log_retention_days", "30")
    cfg.set("log_retention_max_rows", "50000")


# ── REL-6 ────────────────────────────────────────────────────────────────

def test_progress_persist_failures_are_counted_and_exposed(client):
    before = engine.progress_persist_failure_count()

    class _BoomSession:
        async def __aenter__(self):
            raise RuntimeError("simulated DB outage")
        async def __aexit__(self, *a):
            return False

    orig = engine.AsyncSessionLocal
    engine.AsyncSessionLocal = _BoomSession
    try:
        for _ in range(3):
            run_async(engine._update_progress("does-not-matter", 50.0, 1024.0, 10, 2048))
    finally:
        engine.AsyncSessionLocal = orig

    after = engine.progress_persist_failure_count()
    assert after == before + 3

    body = client.get("/api/v1/metrics").text
    assert f"streamvault_progress_persist_failures_total {after}" in body
