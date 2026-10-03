"""SSRF URL validation (utils/url_validator.py)."""
import pytest
from utils.url_validator import validate_url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://example.com",
])
def test_valid_public_urls_pass(url):
    is_valid, reason = validate_url(url)
    assert is_valid, f"{url} rejected: {reason}"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8080/admin",
    "http://192.168.1.1",
    "http://localhost/api",
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
    "file:///etc/passwd",
])
def test_private_and_dangerous_urls_rejected(url):
    is_valid, _ = validate_url(url)
    assert not is_valid


def test_bracketed_ipv6_literal_is_resolved_correctly():
    # Regression test for the FIX-02 bug: a manual netloc.split(":")[0]
    # mangled "[::1]:8080" into "[" instead of recognizing the IPv6 loopback.
    is_valid, reason = validate_url("http://[::1]:8080/")
    assert not is_valid
    assert "resolve" not in reason.lower()  # rejected as private IP, not "could not resolve"


def test_empty_and_malformed_urls_rejected():
    assert not validate_url("")[0]
    assert not validate_url("not a url at all")[0]
