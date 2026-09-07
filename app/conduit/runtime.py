"""Start/stop the loopback Conduit and detect a local Tor SOCKS port."""

from __future__ import annotations

import socket
import threading
from typing import Any

from app.config import CONDUIT_BIND, CONDUIT_PORT
from app.conduit.server import ConduitServer, ConduitHandler, serve_forever_background

_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "bind": CONDUIT_BIND,
    "port": 0,
    "server": None,
    "thread": None,
    "upstream": "",
}


def listen_url() -> str:
    with _lock:
        if _state["running"] and _state["port"]:
            return f"http://{_state['bind']}:{_state['port']}"
    return ""


def tor_socks_detected() -> dict[str, Any]:
    for port in (9050, 9150):
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.25)
            sock.close()
            return {"detected": True, "port": port, "hint": f"socks5://127.0.0.1:{port}"}
        except OSError:
            continue
    return {"detected": False, "port": None, "hint": "Start Tor yourself if you want SOCKS egress. ArgosScout will not launch a hidden service."}


def start_conduit(*, upstream: str = "") -> dict[str, Any]:
    bind = CONDUIT_BIND
    if bind not in {"127.0.0.1", "::1", "localhost"}:
        return {"ok": False, "error": "Conduit may bind loopback only."}
    with _lock:
        if _state["running"]:
            return status()
        httpd = ConduitServer((bind, CONDUIT_PORT), ConduitHandler)
        httpd.upstream_url = upstream or ""
        port = int(httpd.server_address[1])
        thread = serve_forever_background(httpd)
        _state.update(
            running=True,
            bind=bind,
            port=port,
            server=httpd,
            thread=thread,
            upstream=upstream or "",
        )
    return status()


def stop_conduit() -> dict[str, Any]:
    with _lock:
        server = _state.get("server")
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except OSError:
                pass
        _state.update(running=False, port=0, server=None, thread=None, upstream="")
    return status()


def status() -> dict[str, Any]:
    with _lock:
        running = bool(_state["running"])
        port = int(_state["port"] or 0)
        bind = _state["bind"]
        has_upstream = bool(_state.get("upstream"))
    tor = tor_socks_detected()
    return {
        "ok": True,
        "running": running,
        "bind": bind if running else CONDUIT_BIND,
        "port": port,
        "listen": listen_url(),
        "loopback_only": True,
        "upstream_configured": has_upstream,
        "tor": tor,
        "note": (
            "Argos Conduit is a witnessed policy proxy on loopback. "
            "It does not spoof browsers, steal sessions, or rotate residential IPs."
        ),
    }
