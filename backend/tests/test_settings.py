"""Settings API — SEC-5 (redaction of secret-shaped values) and SEC-8
(restart_required surfacing for process-start-only settings)."""
import pytest


@pytest.fixture(autouse=True)
def _restore_proxy(client):
    """Every test in this module writes to the shared `proxy` setting —
    reset it afterward so later test files see a clean slate."""
    yield
    client.post("/api/v1/settings/update", json={"key": "proxy", "value": ""})


def test_sensitive_value_is_masked_in_get_settings(client):
    client.post("/api/v1/settings/update", json={"key": "proxy", "value": "http://user:pass@proxy:8080"})
    body = client.get("/api/v1/settings").json()
    assert body["proxy"]["value"] == "•" * 8
    assert body["proxy"]["is_set"] is True


def test_non_sensitive_values_are_not_masked(client):
    body = client.get("/api/v1/settings").json()
    assert body["default_quality"]["value"] != "•" * 8


def test_masking_also_applies_to_single_setting_lookup(client):
    client.post("/api/v1/settings/update", json={"key": "proxy", "value": "http://secret"})
    r = client.get("/api/v1/settings/proxy")
    assert r.json()["value"] == "•" * 8


def test_unset_sensitive_key_reports_is_set_false(client):
    body = client.get("/api/v1/settings").json()
    assert body["cookies_file"]["is_set"] is False


def test_restart_required_flagged_on_cors_origins(client):
    r = client.post("/api/v1/settings/update", json={"key": "cors_origins", "value": "https://example.com"})
    assert r.json()["restart_required"] is True


def test_restart_required_not_flagged_on_a_normal_setting(client):
    r = client.post("/api/v1/settings/update", json={"key": "audio_format", "value": "flac"})
    assert r.json()["restart_required"] is False


def test_bulk_update_reports_only_the_restart_required_keys(client):
    r = client.post("/api/v1/settings/bulk", json={"db_pool_size": "10", "audio_format": "wav"})
    assert r.json()["restart_required_keys"] == ["db_pool_size"]
