"""Argos Conduit — in-app loopback policy proxy and witnessed quiet (Veil).

This is not anti-detect infrastructure: no canvas noise, no stealth login,
no residential rotation farm, no challenge solver.
"""

from app.conduit.runtime import listen_url, start_conduit, status as conduit_status, stop_conduit
from app.conduit.lantern import is_lantern
from app.conduit.veil import is_veil_on
from app.conduit.witness import list_witness, record_hop

__all__ = [
    "conduit_status",
    "is_lantern",
    "is_veil_on",
    "list_witness",
    "listen_url",
    "record_hop",
    "start_conduit",
    "stop_conduit",
]
