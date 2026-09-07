"""Minimal SOCKS5 CONNECT client (stdlib). Used only to chain Conduit to the operator's Tor/SOCKS."""

from __future__ import annotations

import socket
from urllib.parse import urlparse


def parse_upstream(url: str) -> dict[str, str | int | None]:
    parsed = urlparse((url or "").strip())
    return {
        "scheme": parsed.scheme or "",
        "host": parsed.hostname or "",
        "port": parsed.port,
        "user": parsed.username,
        "password": parsed.password,
    }


def open_via_upstream(upstream: str, dest_host: str, dest_port: int, timeout: float = 15) -> socket.socket:
    info = parse_upstream(upstream)
    scheme = str(info["scheme"])
    host = str(info["host"])
    if not host:
        raise OSError("Upstream proxy host missing")
    port = int(info["port"] or (9050 if scheme.startswith("socks") else 8080))
    if scheme in {"socks5", "socks5h", "socks4"}:
        return _socks5_connect(host, port, dest_host, dest_port, timeout, info.get("user"), info.get("password"))
    # HTTP CONNECT upstream
    sock = socket.create_connection((host, port), timeout=timeout)
    req = f"CONNECT {dest_host}:{dest_port} HTTP/1.1\r\nHost: {dest_host}:{dest_port}\r\n\r\n"
    sock.sendall(req.encode("ascii"))
    buf = b""
    while b"\r\n\r\n" not in buf and len(buf) < 8192:
        chunk = sock.recv(1024)
        if not chunk:
            break
        buf += chunk
    if b" 200 " not in buf.split(b"\r\n", 1)[0]:
        sock.close()
        raise OSError("HTTP upstream CONNECT failed")
    return sock


def _socks5_connect(
    proxy_host: str,
    proxy_port: int,
    dest_host: str,
    dest_port: int,
    timeout: float,
    user: str | None,
    password: str | None,
) -> socket.socket:
    sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    if user:
        sock.sendall(b"\x05\x02\x00\x02")
    else:
        sock.sendall(b"\x05\x01\x00")
    greet = sock.recv(2)
    if len(greet) < 2 or greet[0] != 5:
        sock.close()
        raise OSError("SOCKS5 greeting failed")
    if greet[1] == 2:
        u = (user or "").encode()[:255]
        p = (password or "").encode()[:255]
        sock.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
        auth = sock.recv(2)
        if len(auth) < 2 or auth[1] != 0:
            sock.close()
            raise OSError("SOCKS5 auth failed")
    elif greet[1] != 0:
        sock.close()
        raise OSError("SOCKS5 method not accepted")
    host_b = dest_host.encode("idna")
    req = b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b + dest_port.to_bytes(2, "big")
    sock.sendall(req)
    reply = sock.recv(10)
    if len(reply) < 2 or reply[1] != 0:
        sock.close()
        raise OSError("SOCKS5 CONNECT failed")
    return sock
