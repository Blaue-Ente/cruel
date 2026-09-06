"""SSRF protection for user-supplied outbound URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.config import SSRF_ALLOW_PRIVATE, SSRF_DNS_TIMEOUT_SEC

BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}

BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".corp")

LINK_LOCAL_NETS = (
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fd00::/8"),
    ipaddress.ip_network("fe80::/10"),
)


class UnsafeURLError(ValueError):
    """Raised when an outbound URL is not a public http(s) target."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified or getattr(ip, "is_site_local", False):
        return True
    for net in LINK_LOCAL_NETS:
        if ip in net:
            return True
    return False


def _resolve_host(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(SSRF_DNS_TIMEOUT_SEC)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Host could not be resolved: {host}") from exc
    finally:
        socket.setdefaulttimeout(previous)

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        addresses.append(ipaddress.ip_address(sockaddr[0]))
    if not addresses:
        raise UnsafeURLError(f"Host resolved to no addresses: {host}")
    return addresses


def ensure_safe_url(url: str) -> str:
    """Validate that *url* is http(s) and does not target a private/internal host.

    When SSRF_ALLOW_PRIVATE is true (explicit operator override), only the
    scheme check remains. Redirects must be re-validated by the HTTP client.
    """
    if not url or not isinstance(url, str):
        raise UnsafeURLError("URL is required")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("Only http and https URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL host is required")

    host_l = host.lower().rstrip(".")
    if host_l in BLOCKED_HOSTS or host_l.endswith(BLOCKED_SUFFIXES):
        raise UnsafeURLError(f"Blocked host: {host_l}")

    if SSRF_ALLOW_PRIVATE:
        return url

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        literal_ip = ipaddress.ip_address(host_l)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_blocked_ip(literal_ip):
            raise UnsafeURLError(f"Blocked address: {host_l}")
        return url

    for ip in _resolve_host(host_l, port):
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"Host {host_l} resolved to a private address")

    return url
