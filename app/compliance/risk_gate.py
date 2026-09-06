"""Operator risk gate — high-risk capabilities stay off until an informed opt-in.

The operator must read the notice, confirm authorized use, type the acceptance
phrase, then enable each capability. Nothing here is on by default. Revoking
the acknowledgment turns every flag off.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import RISK_ACK_PATH

NOTICE_VERSION = 1
ACK_PHRASES = ("I ACCEPT THE RISK", "ПРИЕМАМ РИСКА")

CAPABILITIES = (
    "flaresolverr",
    "tls_impersonate",
    "fingerprint_profiles",
    "linkedin_public_fetch",
    "github_commit_emails",
)

NOTICE_EN = """HIGH-RISK OPERATOR OPTIONS — READ BEFORE ENABLING

These switches are off by default. Turning any of them on is your decision and
your legal responsibility. ArgosScout’s authors do not authorize misuse.

1. FlareSolverr (Bring Your Own)
   Talks to a FlareSolverr instance YOU run (typically localhost:8191) to fetch
   a URL that served a bot challenge. ArgosScout does not ship a Cloudflare or
   Turnstile solver. You must have the right to fetch that host.

2. TLS impersonation (optional curl_cffi)
   Uses a Chrome-like TLS/JA3 client profile for outbound GET. This can evade
   naive TLS fingerprint blocks. Use only on hosts you are allowed to test.

3. Coherent browser fingerprints
   Aligns User-Agent, platform, WebGL vendor/renderer, and AudioContext with one
   hardware profile, and may hide navigator.webdriver. This is not a full
   anti-detect pack (no canvas noise, no challenge solver).

4. LinkedIn public fetch
   Attempts an unauthenticated GET of a public LinkedIn URL. Login walls, 999
   blocks, and authenticated-only data are NOT bypassed. LinkedIn’s terms
   generally prohibit scraping. Enable only if you have a lawful basis.

5. GitHub public commit author emails
   Reads author.email from the public GitHub commits API for a repo YOU name.
   Many addresses are users.noreply.github.com. This is personal data under
   GDPR. Do not use it to compile marketing lists or stalk private individuals.

You confirm: you have authorization or another lawful basis; you will not attack
third-party bot defenses, steal sessions, or harvest people at scale; you accept
all liability. Type the phrase exactly, then enable individual options.
"""

NOTICE_BG = """ОПЦИИ С ВИСОК РИСК — ПРОЧЕТЕТЕ ПРЕДИ ВКЛЮЧВАНЕ

По подразбиране всички ключове са изключени. Включването е ваше решение и
ваша правна отговорност.

1. FlareSolverr (свой инстанс) — ArgosScout не носи Cloudflare solver.
2. TLS имитация (curl_cffi) — Chrome-подобен JA3 само към разрешени хостове.
3. Съгласувани браузър профили — UA/WebGL/Audio; не е пълен anti-detect.
4. LinkedIn публично теглене — без логин и без заобикаляне на стена.
5. GitHub публични commit имейли — лични данни; само за посочено от вас хранилище.

Потвърждавате законно основание и приемате цялата отговорност.
Напишете фразата точно, после включете отделните опции.
"""


class RiskCapabilityOff(Exception):
    def __init__(self, capability: str):
        self.capability = capability
        super().__init__(
            f"High-risk capability '{capability}' is off. Read the operator notice, "
            "type the acceptance phrase, and enable the option in Settings."
        )


def _empty_caps() -> dict[str, bool]:
    return {name: False for name in CAPABILITIES}


def _default_state() -> dict[str, Any]:
    return {
        "notice_version": NOTICE_VERSION,
        "acknowledged": False,
        "acknowledged_at": None,
        "authorized_use": False,
        "capabilities": _empty_caps(),
    }


def _load() -> dict[str, Any]:
    if not RISK_ACK_PATH.exists():
        return _default_state()
    try:
        raw = json.loads(RISK_ACK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(raw, dict):
        return _default_state()
    state = _default_state()
    state["acknowledged"] = bool(raw.get("acknowledged")) and raw.get("notice_version") == NOTICE_VERSION
    state["acknowledged_at"] = raw.get("acknowledged_at")
    state["authorized_use"] = bool(raw.get("authorized_use"))
    state["notice_version"] = NOTICE_VERSION
    caps = raw.get("capabilities") if isinstance(raw.get("capabilities"), dict) else {}
    if not state["acknowledged"] or not state["authorized_use"]:
        return state
    for name in CAPABILITIES:
        state["capabilities"][name] = bool(caps.get(name))
    return state


def _save(state: dict[str, Any]) -> dict[str, Any]:
    RISK_ACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "notice_version": NOTICE_VERSION,
        "acknowledged": bool(state.get("acknowledged")),
        "acknowledged_at": state.get("acknowledged_at"),
        "authorized_use": bool(state.get("authorized_use")),
        "capabilities": {name: bool((state.get("capabilities") or {}).get(name)) for name in CAPABILITIES},
    }
    RISK_ACK_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        RISK_ACK_PATH.chmod(0o600)
    except OSError:
        pass
    return _load()


def get_notice() -> dict[str, Any]:
    return {
        "notice_version": NOTICE_VERSION,
        "phrase": ACK_PHRASES[0],
        "phrases_accepted": list(ACK_PHRASES),
        "notice_en": NOTICE_EN,
        "notice_bg": NOTICE_BG,
        "capabilities": [
            {"id": "flaresolverr", "name": "FlareSolverr (BYO instance)"},
            {"id": "tls_impersonate", "name": "TLS/JA3 impersonation (curl_cffi)"},
            {"id": "fingerprint_profiles", "name": "Coherent Canvas/WebGL/Audio profiles"},
            {"id": "linkedin_public_fetch", "name": "LinkedIn public fetch (no login bypass)"},
            {"id": "github_commit_emails", "name": "GitHub public commit author emails"},
        ],
    }


def get_status() -> dict[str, Any]:
    state = _load()
    notice = get_notice()
    return {**notice, **state, "any_enabled": any(state["capabilities"].values())}


def is_enabled(capability: str) -> bool:
    if capability not in CAPABILITIES:
        return False
    state = _load()
    return bool(state["acknowledged"] and state["authorized_use"] and state["capabilities"].get(capability))


def require_capability(capability: str) -> None:
    if not is_enabled(capability):
        raise RiskCapabilityOff(capability)


def acknowledge(
    phrase: str,
    *,
    authorized_use: bool,
    capabilities: Optional[dict[str, bool]] = None,
) -> dict[str, Any]:
    typed = " ".join((phrase or "").strip().split()).upper()
    allowed = {p.upper() for p in ACK_PHRASES}
    if typed not in allowed:
        return {
            **get_status(),
            "ok": False,
            "error": f'Type {ACK_PHRASES[0]} or {ACK_PHRASES[1]} exactly after reading the notice.',
        }
    if not authorized_use:
        return {
            **get_status(),
            "ok": False,
            "error": "Set authorized_use=true — you confirm a lawful basis for these options.",
        }
    caps = _empty_caps()
    incoming = capabilities or {}
    for name in CAPABILITIES:
        caps[name] = bool(incoming.get(name))
    state = {
        "notice_version": NOTICE_VERSION,
        "acknowledged": True,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        "authorized_use": True,
        "capabilities": caps,
    }
    _save(state)
    status = get_status()
    status["ok"] = True
    return status


def update_capabilities(capabilities: dict[str, bool]) -> dict[str, Any]:
    state = _load()
    if not state["acknowledged"] or not state["authorized_use"]:
        return {**get_status(), "ok": False, "error": "Acknowledge the notice before toggling options."}
    caps = dict(state["capabilities"])
    for name in CAPABILITIES:
        if name in capabilities:
            caps[name] = bool(capabilities[name])
    state["capabilities"] = caps
    _save(state)
    status = get_status()
    status["ok"] = True
    return status


def revoke() -> dict[str, Any]:
    _save(_default_state())
    status = get_status()
    status["ok"] = True
    status["revoked"] = True
    return status
