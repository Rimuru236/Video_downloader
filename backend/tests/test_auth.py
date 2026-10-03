"""API key authentication (SEC-1) — HTTP routes and the WebSocket handshake."""
import pytest


@pytest.fixture
def with_api_key(cfg):
    """Enables auth for the duration of a test, guaranteed to disable it
    again afterward regardless of pass/fail — this is a global, shared-app
    setting, so leaking it would break every other test in the session."""
    cfg.set("api_key", "s3cr3t-test-key")
    try:
        yield "s3cr3t-test-key"
    finally:
        cfg.set("api_key", "")


def test_open_by_default(client):
    r = client.get("/api/v1/downloads")
    assert r.status_code == 200


def test_health_always_open(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_locked_down_once_key_is_set(client, with_api_key):
    assert client.get("/api/v1/downloads").status_code == 401
    assert client.get("/api/v1/downloads", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/downloads", headers={"X-API-Key": with_api_key}).status_code == 200


def test_health_stays_open_even_with_key_set(client, with_api_key):
    assert client.get("/health").status_code == 200


def test_settings_endpoint_is_not_exempted(client, with_api_key):
    assert client.get("/api/v1/settings").status_code == 401
    assert client.get("/api/v1/settings", headers={"X-API-Key": with_api_key}).status_code == 200


def test_websocket_rejected_without_key(client, with_api_key):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/download/fake-id"):
            pass


def test_websocket_rejected_with_wrong_key(client, with_api_key):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/download/fake-id?api_key=wrong"):
            pass


def test_websocket_accepted_with_correct_key(client, with_api_key):
    with client.websocket_connect(f"/api/v1/ws/download/fake-id?api_key={with_api_key}"):
        pass  # connecting without raising is the assertion


def test_disabling_key_reopens_access(client, cfg):
    cfg.set("api_key", "temp-key")
    assert client.get("/api/v1/downloads").status_code == 401
    cfg.set("api_key", "")
    assert client.get("/api/v1/downloads").status_code == 200
