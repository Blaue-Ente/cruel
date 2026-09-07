"""Lantern vs Veil lanes.

Lantern hosts are public bibliographic / registry APIs. Veil does not hide
them: they stay identified, lightly witnessed, and may skip quiet-jitter.
"""

from __future__ import annotations

from urllib.parse import urlparse

LANTERN_SUFFIXES = (
    "openalex.org",
    "crossref.org",
    "arxiv.org",
    "archive.org",
    "sec.gov",
    "companieshouse.gov.uk",
    "opencorporates.com",
    "wikipedia.org",
    "wikidata.org",
    "iana.org",
)


def hostname(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_lantern(url: str) -> bool:
    host = hostname(url)
    if not host:
        return False
    return any(host == sfx or host.endswith("." + sfx) for sfx in LANTERN_SUFFIXES)
