from __future__ import annotations

import ipaddress

import pytest

from app.security.rate_limit import RateLimiter
from app.security.ssrf import UnsafeURLError, ensure_safe_url


def test_blocks_file_scheme():
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("file:///etc/passwd")


def test_blocks_loopback_literal():
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("http://127.0.0.1/admin")


def test_blocks_metadata_ip():
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("http://169.254.169.254/latest/meta-data")


def test_blocks_localhost_hostname():
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("http://localhost:8000/health")


def test_blocks_ipv6_loopback():
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("http://[::1]/")


def test_blocks_credentials_in_url():
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("https://user:pass@example.com/")


def test_blocks_hostname_that_resolves_private(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(2, 1, 6, "", ("10.0.0.8", port or 80))]

    monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeURLError):
        ensure_safe_url("https://internal.corp.example")


def test_allows_public_literal():
    # 1.1.1.1 is public Cloudflare DNS — no DNS lookup required.
    assert ensure_safe_url("https://1.1.1.1/cdn-cgi/trace").startswith("https://")
    ipaddress.ip_address("1.1.1.1")


def test_rate_limiter_trips():
    limiter = RateLimiter(limit=3, window_sec=60)
    assert limiter.allow("a")[0] is True
    assert limiter.allow("a")[0] is True
    assert limiter.allow("a")[0] is True
    allowed, remaining, retry = limiter.allow("a")
    assert allowed is False
    assert remaining == 0
    assert retry >= 1
    assert limiter.allow("b")[0] is True
