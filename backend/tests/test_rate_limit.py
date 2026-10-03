"""Per-client rate limiting middleware (SEC-4).

The limiter's hit-tracking dict is genuinely global/shared state within a
process (that's correct production behavior — it's what makes the limit
mean something), which means it's also shared across this whole pytest
session's single TestClient identity. Rather than fight that, each test
here uses its own unique X-API-Key header — the middleware keys its bucket
on the API key when one is present, so this gives every test a fresh,
untouched bucket regardless of what earlier tests (in this file or any
other) already did against the shared "testclient" IP identity. Sending an
arbitrary key here doesn't trigger auth (see test_auth.py) since no
api_key is configured in these tests.
"""
import itertools

import pytest

_counter = itertools.count()


def _fresh_headers():
    return {"X-API-Key": f"rate-limit-test-{next(_counter)}"}


@pytest.fixture
def with_low_limit(cfg):
    cfg.set("api_rate_limit_per_min", "3")
    try:
        yield
    finally:
        cfg.set("api_rate_limit_per_min", "300")  # restore the app default


def test_requests_within_limit_succeed(client, with_low_limit):
    headers = _fresh_headers()
    for _ in range(3):
        assert client.get("/api/v1/downloads", headers=headers).status_code == 200


def test_exceeding_the_limit_returns_429_with_retry_after(client, with_low_limit):
    headers = _fresh_headers()
    for _ in range(3):
        client.get("/api/v1/downloads", headers=headers)
    r = client.get("/api/v1/downloads", headers=headers)
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}


def test_health_is_exempt_from_rate_limiting(client, with_low_limit):
    headers = _fresh_headers()
    for _ in range(3):
        client.get("/api/v1/downloads", headers=headers)
    assert client.get("/health", headers=headers).status_code == 200


def test_zero_disables_rate_limiting(client, cfg):
    headers = _fresh_headers()
    cfg.set("api_rate_limit_per_min", "0")
    try:
        for _ in range(6):
            assert client.get("/api/v1/downloads", headers=headers).status_code == 200
    finally:
        cfg.set("api_rate_limit_per_min", "300")
