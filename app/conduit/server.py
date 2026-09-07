"""Loopback HTTP/CONNECT proxy. Binds 127.0.0.1 only. SSRF on every destination."""

from __future__ import annotations

import select
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.conduit.lantern import is_lantern
from app.conduit.socks import open_via_upstream
from app.conduit.witness import record_hop
from app.security.ssrf import UnsafeURLError, ensure_safe_url

_TUNNEL_TIMEOUT = 30


class ConduitHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *args) -> None:  # noqa: ARG002
        return

    def _upstream(self) -> str:
        return getattr(self.server, "upstream_url", "") or ""

    def do_CONNECT(self) -> None:  # noqa: N802
        host_port = (self.path or "").split(":", 1)
        host = host_port[0]
        try:
            port = int(host_port[1]) if len(host_port) > 1 else 443
        except ValueError:
            self.send_error(400, "Bad CONNECT")
            return
        target = f"https://{host}/"
        try:
            ensure_safe_url(target)
        except UnsafeURLError as exc:
            record_hop(method="CONNECT", url=target, status=403, lane="blocked", note=str(exc)[:120])
            self.send_error(403, "Destination blocked")
            return
        try:
            remote = self._open_remote(host, port)
        except OSError as exc:
            record_hop(method="CONNECT", url=target, status=502, lane="veil", note=str(exc)[:120])
            self.send_error(502, "Upstream failed")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        record_hop(method="CONNECT", url=target, status=200, lane="lantern" if is_lantern(target) else "veil")
        _tunnel(self.connection, remote)

    def do_GET(self) -> None:  # noqa: N802
        self._forward()

    def do_HEAD(self) -> None:  # noqa: N802
        self._forward()

    def do_POST(self) -> None:  # noqa: N802
        self.send_error(405, "Conduit forwards GET/HEAD/CONNECT only")

    def _forward(self) -> None:
        url = self.path
        if not url.startswith("http://"):
            self.send_error(400, "Absolute URL required")
            return
        try:
            ensure_safe_url(url)
        except UnsafeURLError as exc:
            record_hop(method=self.command, url=url, status=403, lane="blocked", note=str(exc)[:120])
            self.send_error(403, "Destination blocked")
            return
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 80
        try:
            remote = self._open_remote(host, port)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            req = f"{self.command} {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
            remote.sendall(req.encode("ascii", errors="replace"))
            data = b""
            while True:
                chunk = remote.recv(8192)
                if not chunk:
                    break
                data += chunk
                if len(data) > 2_000_000:
                    break
            remote.close()
        except OSError as exc:
            record_hop(method=self.command, url=url, status=502, lane="veil", note=str(exc)[:120])
            self.send_error(502, "Forward failed")
            return
        self.wfile.write(data)
        status = 200
        if data.startswith(b"HTTP/"):
            try:
                status = int(data.split(b" ", 2)[1])
            except (IndexError, ValueError):
                status = 200
        record_hop(
            method=self.command,
            url=url,
            status=status,
            lane="lantern" if is_lantern(url) else "veil",
            bytes_out=len(data),
        )

    def _open_remote(self, host: str, port: int) -> socket.socket:
        upstream = self._upstream()
        if upstream:
            return open_via_upstream(upstream, host, port, timeout=15)
        return socket.create_connection((host, port), timeout=15)


def _tunnel(client: socket.socket, remote: socket.socket) -> None:
    sockets = [client, remote]
    try:
        while True:
            readable, _, errored = select.select(sockets, [], sockets, _TUNNEL_TIMEOUT)
            if errored or not readable:
                break
            for sock in readable:
                other = remote if sock is client else client
                data = sock.recv(8192)
                if not data:
                    return
                other.sendall(data)
    except OSError:
        return
    finally:
        try:
            remote.close()
        except OSError:
            pass


class ConduitServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    upstream_url = ""


def serve_forever_background(server: ConduitServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, name="argos-conduit", daemon=True)
    thread.start()
    return thread
