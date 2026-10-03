"""OBS-4: GET /analytics/detailed — real aggregations, no Math.random()."""
from datetime import datetime, timezone

from conftest import run_async
from database.db_manager import AsyncSessionLocal
from database.models import Download, DownloadStatus


def _make(status=DownloadStatus.COMPLETED, source_site=None, container_format=None,
          audio_format=None, filesize=0, speed=None):
    async def _create():
        async with AsyncSessionLocal() as session:
            dl = Download(
                url="https://x/analytics-probe", status=status, source_site=source_site,
                container_format=container_format, audio_format=audio_format,
                filesize=filesize, speed=speed, created_at=datetime.now(timezone.utc),
            )
            session.add(dl)
            await session.commit()
            return dl.id
    return run_async(_create())


def test_detailed_analytics_has_the_expected_shape(client):
    r = client.get("/api/v1/analytics/detailed")
    assert r.status_code == 200
    body = r.json()
    assert len(body["daily"]) == 30
    assert set(body["daily"][0]) == {"date", "count", "bytes"}
    assert isinstance(body["platforms"], list)
    assert isinstance(body["formats"], list)
    assert "peak_speed" in body


def test_daily_bucket_reflects_a_download_created_today(client):
    _make(source_site="youtube", filesize=1000)
    r = client.get("/api/v1/analytics/detailed")
    today = body_today = r.json()["daily"][-1]  # last entry is always "today" (since=29 days ago .. today)
    assert today["count"] >= 1


def test_platform_breakdown_reflects_real_source_sites(client):
    _make(source_site="my-unique-test-platform")
    _make(source_site="my-unique-test-platform")
    r = client.get("/api/v1/analytics/detailed")
    sites = {p["site"]: p["count"] for p in r.json()["platforms"]}
    assert sites.get("my-unique-test-platform") == 2


def test_format_breakdown_coalesces_container_and_audio_format(client):
    _make(container_format="mkv-unique-test")
    _make(audio_format="flac-unique-test")
    r = client.get("/api/v1/analytics/detailed")
    formats = {f["format"] for f in r.json()["formats"]}
    assert "mkv-unique-test" in formats
    assert "flac-unique-test" in formats


def test_peak_speed_reflects_the_real_max(client):
    _make(speed=999999.0)
    r = client.get("/api/v1/analytics/detailed")
    assert r.json()["peak_speed"] >= 999999.0
