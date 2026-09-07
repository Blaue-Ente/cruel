"""Operator risk gate — high-risk capabilities stay off until an informed opt-in.

The operator must read the notice, confirm authorized use, type the acceptance
phrase, then enable each capability. High-risk *egress* also requires a
Bring-Your-Own HTTP/SOCKS proxy. Nothing here is on by default. Revoking the
acknowledgment turns every flag off and clears the proxy.

ArgosScout does not ship exploits, stealth logins, or credential stuffing.
Authorized surface enumeration maps public HTTP paths on a host you may test.
Argos Conduit is a loopback policy proxy with a Witness Ledger — quiet, not invisible.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from app.config import RISK_ACK_PATH

NOTICE_VERSION = 3
ACK_PHRASES = ("I ACCEPT THE RISK", "ПРИЕМАМ РИСКА")

CAPABILITIES = (
    "flaresolverr",
    "tls_impersonate",
    "fingerprint_profiles",
    "linkedin_public_fetch",
    "github_commit_emails",
    "authorized_surface_enum",
    "argos_conduit",
    "argos_veil",
)

# These talk to third-party hosts and must egress via operator proxy or Conduit.
PROXY_REQUIRED = (
    "tls_impersonate",
    "linkedin_public_fetch",
    "github_commit_emails",
    "authorized_surface_enum",
    "argos_veil",
)

PROXY_SCHEMES = ("http", "https", "socks4", "socks5", "socks5h")

NOTICE_EN = """HIGH-RISK OPERATOR OPTIONS — READ BEFORE ENABLING

These switches are off by default. Turning any of them on is your decision and
your legal responsibility. ArgosScout’s authors do not authorize misuse.

A Bring-Your-Own PROXY **or Argos Conduit** is required for options that contact
third-party hosts (LinkedIn public GET, GitHub commit emails, TLS impersonation,
authorized surface enumeration, Argos Veil). Conduit is a loopback policy proxy
with a Witness Ledger. You still own the upstream IP (direct, corporate proxy,
or a Tor client YOU start). ArgosScout does not ship residential rotation,
canvas-noise anti-detect, stealth login, or a Cloudflare solver.

1. FlareSolverr (Bring Your Own)
   Talks to a FlareSolverr instance YOU run (typically localhost:8191) to fetch
   a URL that served a bot challenge. ArgosScout does not ship a Cloudflare or
   Turnstile solver. You must have the right to fetch that host.

2. TLS impersonation (optional curl_cffi) — requires proxy or Conduit
   Uses a Chrome-like TLS/JA3 client profile for outbound GET via your egress.
   This can evade naive TLS fingerprint blocks. Use only on hosts you are
   allowed to test. Not a WAF exploit.

3. Coherent browser fingerprints
   Aligns User-Agent, platform, WebGL vendor/renderer, and AudioContext with one
   hardware profile, and may hide navigator.webdriver. This is not a full
   anti-detect pack (no canvas noise, no challenge solver, no stealth login).

4. LinkedIn public fetch — requires proxy or Conduit
   Attempts an unauthenticated GET of a public LinkedIn URL through your egress.
   Login walls, 999 blocks, and authenticated-only data are NOT bypassed.
   LinkedIn’s terms generally prohibit scraping. Enable only if you have a
   lawful basis. No session theft.

5. GitHub public commit author emails — requires proxy or Conduit
   Reads author.email from the public GitHub commits API for a repo YOU name.
   Many addresses are users.noreply.github.com. This is personal data under
   GDPR. Named repository only — not a GitHub-wide person hunt, not credential
   stuffing, not breach-list scraping.

6. Authorized surface enumeration — requires proxy or Conduit AND authorized_target
   Live Active Probe / HTTP path mapping on a host you confirm you may test.
   Discovers same-origin /api paths from public HTML. No exploit payloads, no
   auth bypass, no ransomware tooling. Dry-run stays available without this flag.

7. Argos Conduit (in-app proxy function)
   Starts a loopback-only HTTP/CONNECT proxy. Every hop is written to a
   hash-chained Witness Ledger. Optional upstream: YOUR proxy URL, or a local
   Tor SOCKS port YOU already run (9050/9150). ArgosScout will not launch Tor
   or bind on a public interface.

8. Argos Veil (witnessed quiet) — requires proxy or Conduit
   Split-horizon: public bibliographic APIs stay on the Lantern lane (identified).
   Live third-party fetches go quiet — jitter, DNT/GPC, no extra product headers,
   isolated cookies, Witness Ledger. This is anti-correlation, not invisibility.
   Not deniable: the ledger exists so you can prove what left the box.
   No stealth login, no canvas noise, no challenge solver.

You confirm: you have authorization or another lawful basis; the egress is yours;
you will not attack third-party bot defenses, steal sessions, or harvest people
at scale; you accept all liability. Type the phrase exactly, then enable
individual options.
"""

NOTICE_BG = """ОПЦИИ С ВИСОК РИСК — ПРОЧЕТЕТЕ ПРЕДИ ВКЛЮЧВАНЕ

По подразбиране всички ключове са изключени. Включването е ваше решение и
ваша правна отговорност.

За опции към чужди хостове е задължителен ВАШ HTTP/SOCKS прокси или Argos Conduit
(loopback policy proxy с Witness Ledger). ArgosScout не върти residential IP-та,
не прави stealth login и не пълни credentials.

1. FlareSolverr (свой инстанс) — ArgosScout не носи Cloudflare solver.
2. TLS имитация (curl_cffi) — през вашия egress, само към разрешени хостове.
3. Съгласувани браузър профили — UA/WebGL/Audio; не е пълен anti-detect.
4. LinkedIn публично теглене — през egress; без логин и без заобикаляне на стена.
5. GitHub публични commit имейли — лични данни; само за посочено хранилище.
6. Оторизирано картиране на повърхност — live probe само с authorized_target;
   без exploit payloads.
7. Argos Conduit — локален прокси само на loopback, с одитен ledger.
8. Argos Veil — тиха колекция (jitter + ledger). Не е невидимост и не е deniable.

Потвърждавате законно основание, че egress е ваш, и приемате цялата отговорност.
Напишете фразата точно, после включете отделните опции.
"""


class RiskCapabilityOff(Exception):
    def __init__(self, capability: str):
        self.capability = capability
        super().__init__(
            f"High-risk capability '{capability}' is off. Read the operator notice, "
            "type the acceptance phrase, and enable the option in Settings."
        )


class ProxyRequired(Exception):
    def __init__(self, capability: str = "operator_proxy"):
        self.capability = capability
        super().__init__(
            "High-risk egress requires your HTTP/SOCKS proxy or a running Argos Conduit. "
            "Set proxy_url in Settings or start Conduit after enabling it "
            "(e.g. socks5://127.0.0.1:9050)."
        )


def _empty_caps() -> dict[str, bool]:
    return {name: False for name in CAPABILITIES}


def _default_state() -> dict[str, Any]:
    return {
        "notice_version": NOTICE_VERSION,
        "acknowledged": False,
        "acknowledged_at": None,
        "authorized_use": False,
        "proxy_url": "",
        "capabilities": _empty_caps(),
    }


def validate_proxy_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in PROXY_SCHEMES:
        raise ValueError("Proxy must be http(s) or socks4/socks5, e.g. socks5://127.0.0.1:9050")
    if not parsed.hostname:
        raise ValueError("Proxy host is required.")
    if parsed.path not in ("", "/"):
        raise ValueError("Proxy URL must not include a path.")
    return text


def redact_proxy(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = "***@" if parsed.username else ""
    return f"{parsed.scheme}://{auth}{host}{port}"


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
    try:
        state["proxy_url"] = validate_proxy_url(str(raw.get("proxy_url") or ""))
    except ValueError:
        state["proxy_url"] = ""
    caps = raw.get("capabilities") if isinstance(raw.get("capabilities"), dict) else {}
    if not state["acknowledged"] or not state["authorized_use"]:
        return state
    for name in CAPABILITIES:
        state["capabilities"][name] = bool(caps.get(name))
    return state


def _save(state: dict[str, Any]) -> dict[str, Any]:
    RISK_ACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        proxy = validate_proxy_url(str(state.get("proxy_url") or ""))
    except ValueError:
        proxy = ""
    payload = {
        "notice_version": NOTICE_VERSION,
        "acknowledged": bool(state.get("acknowledged")),
        "acknowledged_at": state.get("acknowledged_at"),
        "authorized_use": bool(state.get("authorized_use")),
        "proxy_url": proxy,
        "capabilities": {name: bool((state.get("capabilities") or {}).get(name)) for name in CAPABILITIES},
    }
    RISK_ACK_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        RISK_ACK_PATH.chmod(0o600)
    except OSError:
        pass
    return _load()


def _capability_catalog() -> list[dict[str, Any]]:
    return [
        {"id": "flaresolverr", "name": "FlareSolverr (BYO instance)", "proxy_required": False},
        {"id": "tls_impersonate", "name": "TLS/JA3 impersonation (curl_cffi)", "proxy_required": True},
        {"id": "fingerprint_profiles", "name": "Coherent Canvas/WebGL/Audio profiles", "proxy_required": False},
        {"id": "linkedin_public_fetch", "name": "LinkedIn public fetch via your proxy (no login bypass)", "proxy_required": True},
        {"id": "github_commit_emails", "name": "GitHub public commit author emails via your proxy", "proxy_required": True},
        {
            "id": "authorized_surface_enum",
            "name": "Authorized HTTP surface enumeration (live probe, no exploits)",
            "proxy_required": True,
        },
        {
            "id": "argos_conduit",
            "name": "Argos Conduit (loopback policy proxy + Witness Ledger)",
            "proxy_required": False,
        },
        {
            "id": "argos_veil",
            "name": "Argos Veil (witnessed quiet / lantern split) — requires proxy or Conduit",
            "proxy_required": True,
        },
    ]


def get_notice() -> dict[str, Any]:
    return {
        "notice_version": NOTICE_VERSION,
        "phrase": ACK_PHRASES[0],
        "phrases_accepted": list(ACK_PHRASES),
        "notice_en": NOTICE_EN,
        "notice_bg": NOTICE_BG,
        "proxy_required_for": list(PROXY_REQUIRED),
        "capabilities": _capability_catalog(),
    }


def get_status() -> dict[str, Any]:
    state = _load()
    notice = get_notice()
    return {
        **notice,
        "acknowledged": state["acknowledged"],
        "acknowledged_at": state["acknowledged_at"],
        "authorized_use": state["authorized_use"],
        "capabilities": state["capabilities"],
        "proxy_configured": bool(state["proxy_url"]) or bool(_conduit_listen()),
        "proxy_redacted": redact_proxy(state["proxy_url"]) or _conduit_redacted(),
        "proxy_source": ("operator" if state["proxy_url"] else ("conduit" if _conduit_listen() else "")),
        "any_enabled": any(state["capabilities"].values()),
    }


def _conduit_listen() -> str:
    try:
        from app.conduit.runtime import listen_url

        return listen_url() or ""
    except Exception:
        return ""


def _conduit_redacted() -> str:
    url = _conduit_listen()
    return redact_proxy(url) if url else ""


def get_operator_proxy_url() -> str:
    return _load().get("proxy_url") or ""


def get_proxy_url() -> str:
    stored = get_operator_proxy_url()
    if stored:
        return stored
    return _conduit_listen()


def operator_proxies() -> Optional[dict[str, str]]:
    url = get_proxy_url()
    if not url:
        return None
    return {"http": url, "https": url}


def is_armed(capability: str) -> bool:
    """Notice accepted and the switch is on — does not require live egress yet."""
    if capability not in CAPABILITIES:
        return False
    state = _load()
    return bool(state["acknowledged"] and state["authorized_use"] and state["capabilities"].get(capability))


def is_enabled(capability: str) -> bool:
    if not is_armed(capability):
        return False
    if capability in PROXY_REQUIRED and not get_proxy_url():
        return False
    return True


def require_capability(capability: str) -> None:
    if capability in PROXY_REQUIRED and not get_proxy_url():
        state = _load()
        if state["acknowledged"] and state["authorized_use"] and state["capabilities"].get(capability):
            raise ProxyRequired(capability)
    if not is_enabled(capability):
        raise RiskCapabilityOff(capability)


def require_proxy(capability: str = "operator_proxy") -> str:
    url = get_proxy_url()
    if not url:
        raise ProxyRequired(capability)
    return url


def acknowledge(
    phrase: str,
    *,
    authorized_use: bool,
    capabilities: Optional[dict[str, bool]] = None,
    proxy_url: str = "",
) -> dict[str, Any]:
    typed = " ".join((phrase or "").strip().split()).upper()
    allowed = {p.upper() for p in ACK_PHRASES}
    if typed not in allowed:
        return {
            **get_status(),
            "ok": False,
            "error": f"Type {ACK_PHRASES[0]} or {ACK_PHRASES[1]} exactly after reading the notice.",
        }
    if not authorized_use:
        return {
            **get_status(),
            "ok": False,
            "error": "Set authorized_use=true — you confirm a lawful basis for these options.",
        }
    try:
        proxy = validate_proxy_url(proxy_url)
    except ValueError as exc:
        return {**get_status(), "ok": False, "error": str(exc)}
    caps = _empty_caps()
    incoming = capabilities or {}
    conduit_on = bool(incoming.get("argos_conduit"))
    for name in CAPABILITIES:
        want = bool(incoming.get(name))
        if want and name in PROXY_REQUIRED and not proxy and not conduit_on:
            return {
                **get_status(),
                "ok": False,
                "error": f"{name} requires proxy_url or Argos Conduit that you operate.",
            }
        caps[name] = want
    state = {
        "notice_version": NOTICE_VERSION,
        "acknowledged": True,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        "authorized_use": True,
        "proxy_url": proxy,
        "capabilities": caps,
    }
    _save(state)
    status = get_status()
    status["ok"] = True
    return status


def update_capabilities(
    capabilities: dict[str, bool],
    *,
    proxy_url: Optional[str] = None,
) -> dict[str, Any]:
    state = _load()
    if not state["acknowledged"] or not state["authorized_use"]:
        return {**get_status(), "ok": False, "error": "Acknowledge the notice before toggling options."}
    if proxy_url is not None:
        try:
            state["proxy_url"] = validate_proxy_url(proxy_url)
        except ValueError as exc:
            return {**get_status(), "ok": False, "error": str(exc)}
    caps = dict(state["capabilities"])
    for name in CAPABILITIES:
        if name in capabilities:
            caps[name] = bool(capabilities[name])
    wants_proxy = any(caps.get(name) for name in PROXY_REQUIRED)
    if wants_proxy and not state["proxy_url"] and not caps.get("argos_conduit") and not _conduit_listen():
        return {
            **get_status(),
            "ok": False,
            "error": "Set proxy_url or enable Argos Conduit before LinkedIn, GitHub emails, TLS impersonation, live surface enumeration, or Veil.",
        }
    state["capabilities"] = caps
    _save(state)
    status = get_status()
    status["ok"] = True
    return status


def revoke() -> dict[str, Any]:
    try:
        from app.conduit.runtime import stop_conduit

        stop_conduit()
    except Exception:
        pass
    _save(_default_state())
    status = get_status()
    status["ok"] = True
    status["revoked"] = True
    return status
