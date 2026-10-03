"""ARCH-5: /ready checks DB connectivity, FFmpeg presence, and disk
headroom — not just "the process is up" like /health."""


def test_ready_returns_200_with_all_checks_when_healthy(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert set(body["checks"]) == {"database", "ffmpeg", "disk"}
    assert body["checks"]["database"]["ok"] is True


def test_ready_is_exempt_from_auth(client, cfg):
    cfg.set("api_key", "some-key")
    try:
        assert client.get("/ready").status_code in (200, 503)  # never 401
    finally:
        cfg.set("api_key", "")


def test_ready_returns_503_when_disk_check_fails(client, cfg):
    cfg.set("ready_min_disk_bytes", str(10 ** 18))  # absurdly high — nothing has this much free
    try:
        r = client.get("/ready")
        assert r.status_code == 503
        assert r.json()["status"] == "not_ready"
        assert r.json()["checks"]["disk"]["ok"] is False
    finally:
        cfg.set("ready_min_disk_bytes", "524288000")
