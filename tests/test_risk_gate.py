from __future__ import annotations

import json

import pytest

from app.browser.fingerprint import fingerprint_init_script
from app.compliance.risk_gate import (
    CAPABILITIES,
    NOTICE_VERSION,
    acknowledge,
    get_notice,
    get_status,
    is_armed,
    is_enabled,
    require_capability,
    revoke,
    RiskCapabilityOff,
    update_capabilities,
    validate_proxy_url,
)
from app.http_impersonate import impersonate_get
from app.osint.github_emails import parse_repo, public_commit_emails
from app.osint.linkedin import fetch_linkedin_public
from app.recon.flaresolverr import fetch_via_flaresolverr


@pytest.fixture(autouse=True)
def isolated_risk_ack(tmp_path, monkeypatch):
    path = tmp_path / "risk_ack.json"
    monkeypatch.setattr("app.compliance.risk_gate.RISK_ACK_PATH", path)
    monkeypatch.setattr("app.config.RISK_ACK_PATH", path)
    yield path


def test_capabilities_off_by_default():
    status = get_status()
    assert status["acknowledged"] is False
    assert status["any_enabled"] is False
    for name in CAPABILITIES:
        assert status["capabilities"][name] is False
        assert is_enabled(name) is False
        with pytest.raises(RiskCapabilityOff):
            require_capability(name)


def test_notice_is_public_shaped():
    notice = get_notice()
    assert "FlareSolverr" in notice["notice_en"]
    assert "ПРИЕМАМ РИСКА" in notice["phrases_accepted"]
    assert notice["notice_version"] == 3
    assert NOTICE_VERSION == 3
    ids = {c["id"] for c in notice["capabilities"]}
    assert ids == set(CAPABILITIES)
    assert "authorized_surface_enum" in ids
    assert "linkedin_public_fetch" in notice["proxy_required_for"]
    assert "argos_veil" in notice["proxy_required_for"]
    assert "argos_conduit" not in notice["proxy_required_for"]
    assert "Argos Conduit" in notice["notice_en"]
    assert "Argos Veil" in notice["notice_en"]
    assert "Witness Ledger" in notice["notice_en"]


def test_ack_rejects_wrong_phrase():
    result = acknowledge("sure", authorized_use=True)
    assert result["ok"] is False
    assert is_enabled("flaresolverr") is False


def test_ack_rejects_without_authorized_use():
    result = acknowledge("I ACCEPT THE RISK", authorized_use=False)
    assert result["ok"] is False
    assert result["acknowledged"] is False


def test_ack_english_then_enable_one_flag():
    result = acknowledge("  i accept the risk  ", authorized_use=True)
    assert result["ok"] is True
    assert result["acknowledged"] is True
    assert result["any_enabled"] is False
    assert is_enabled("tls_impersonate") is False
    no_proxy = update_capabilities({"tls_impersonate": True, "flaresolverr": False})
    assert no_proxy["ok"] is False
    assert is_enabled("tls_impersonate") is False
    updated = update_capabilities(
        {"tls_impersonate": True, "flaresolverr": False},
        proxy_url="socks5://127.0.0.1:9050",
    )
    assert updated["ok"] is True
    assert is_enabled("tls_impersonate") is True
    assert is_enabled("flaresolverr") is False
    assert updated["proxy_configured"] is True
    assert updated["proxy_redacted"] == "socks5://127.0.0.1:9050"


def test_ack_bulgarian_phrase():
    result = acknowledge("приемам риска", authorized_use=True)
    assert result["ok"] is True
    assert result["authorized_use"] is True


def test_update_caps_before_ack_fails():
    result = update_capabilities({"linkedin_public_fetch": True})
    assert result["ok"] is False
    assert is_enabled("linkedin_public_fetch") is False


def test_revoke_clears_everything():
    acknowledge(
        "I ACCEPT THE RISK",
        authorized_use=True,
        capabilities={"github_commit_emails": True},
        proxy_url="socks5://127.0.0.1:9050",
    )
    assert is_enabled("github_commit_emails") is True
    revoke()
    assert is_enabled("github_commit_emails") is False
    assert get_status()["acknowledged"] is False
    assert get_status()["proxy_configured"] is False


def test_ack_file_mode_600(isolated_risk_ack):
    acknowledge("I ACCEPT THE RISK", authorized_use=True)
    mode = isolated_risk_ack.stat().st_mode & 0o777
    assert mode == 0o600
    payload = json.loads(isolated_risk_ack.read_text())
    assert payload["notice_version"] == 3


def test_disabled_clients_do_not_call_out():
    assert fetch_via_flaresolverr("https://example.com")["disabled"] is True
    assert impersonate_get("https://example.com")["disabled"] is True
    assert fetch_linkedin_public("https://www.linkedin.com/in/someone")["disabled"] is True
    assert public_commit_emails("octocat", "Hello-World")["disabled"] is True


def test_parse_repo_from_url():
    assert parse_repo("https://github.com/octocat/Hello-World.git", "") == ("octocat", "Hello-World")
    assert parse_repo("octocat", "Hello-World") == ("octocat", "Hello-World")


def test_fingerprint_script_is_coherent_not_canvas_noise():
    script = fingerprint_init_script("desktop_chrome")
    assert "webdriver" in script
    assert "37445" in script
    assert "37446" in script
    assert "toDataURL" not in script
    assert "getImageData" not in script
    assert "toBlob" not in script


def test_health_risk_summary_hides_flags(client):
    r = client.get("/health")
    assert r.status_code == 200
    risk = r.json()["risk"]
    assert set(risk) == {"acknowledged", "any_enabled", "proxy_configured"}
    assert risk["acknowledged"] is False
    assert risk["any_enabled"] is False
    assert risk["proxy_configured"] is False
    dumped = json.dumps(risk)
    assert "flaresolverr" not in dumped
    assert "linkedin" not in dumped


def test_remote_flaresolverr_requires_flag(monkeypatch):
    monkeypatch.setattr("app.recon.flaresolverr.FLARESOLVERR_URL", "https://solver.example")
    monkeypatch.setattr("app.recon.flaresolverr.FLARESOLVERR_ALLOW_REMOTE", False)
    from app.recon.flaresolverr import flaresolverr_configured

    assert flaresolverr_configured() is False
    monkeypatch.setattr("app.recon.flaresolverr.FLARESOLVERR_ALLOW_REMOTE", True)
    assert flaresolverr_configured() is True


def test_notice_endpoint_is_public(client):
    r = client.get("/api/v1/compliance/risk")
    assert r.status_code == 200
    body = r.json()
    assert "notice_en" in body
    assert "acknowledged" not in body


def test_status_requires_api_key(client):
    r = client.get("/api/v1/compliance/risk/status")
    assert r.status_code == 401


def test_high_risk_apis_403_until_enabled(client, api_key):
    headers = {"X-API-Key": api_key}
    blocked = [
        ("/api/v1/recon/flaresolverr", {"url": "https://example.com"}),
        ("/api/v1/osint/linkedin", {"url": "https://www.linkedin.com/in/example"}),
        ("/api/v1/osint/github-emails", {"owner": "octocat", "repo": "Hello-World"}),
    ]
    for path, payload in blocked:
        r = client.post(path, headers=headers, json=payload)
        assert r.status_code == 403, path
        assert "capability" in r.json()

    bad = client.post(
        "/api/v1/compliance/risk/acknowledge",
        headers=headers,
        json={"phrase": "not the phrase", "authorized_use": True},
    )
    assert bad.status_code == 400

    no_auth = client.post(
        "/api/v1/compliance/risk/acknowledge",
        headers=headers,
        json={"phrase": "I ACCEPT THE RISK", "authorized_use": False},
    )
    assert no_auth.status_code == 400

    ack = client.post(
        "/api/v1/compliance/risk/acknowledge",
        headers=headers,
        json={"phrase": "I ACCEPT THE RISK", "authorized_use": True, "capabilities": {}},
    )
    assert ack.status_code == 200
    assert ack.json()["acknowledged"] is True
    assert ack.json()["any_enabled"] is False

    still = client.post(
        "/api/v1/osint/github-emails",
        headers=headers,
        json={"owner": "octocat", "repo": "Hello-World"},
    )
    assert still.status_code == 403

    caps = client.post(
        "/api/v1/compliance/risk/capabilities",
        headers=headers,
        json={"capabilities": {"github_commit_emails": True}},
    )
    assert caps.status_code == 400
    assert "proxy" in (caps.json().get("detail") or "").lower()

    caps = client.post(
        "/api/v1/compliance/risk/capabilities",
        headers=headers,
        json={"capabilities": {"github_commit_emails": True}, "proxy_url": "socks5://127.0.0.1:9050"},
    )
    assert caps.status_code == 200
    assert caps.json()["capabilities"]["github_commit_emails"] is True
    assert caps.json()["proxy_configured"] is True

    missing = client.post("/api/v1/osint/github-emails", headers=headers, json={})
    assert missing.status_code == 400

    revoked = client.post("/api/v1/compliance/risk/revoke", headers=headers)
    assert revoked.status_code == 200
    again = client.post(
        "/api/v1/osint/github-emails",
        headers=headers,
        json={"owner": "octocat", "repo": "Hello-World"},
    )
    assert again.status_code == 403


def test_proxy_url_validation():
    assert validate_proxy_url("socks5://127.0.0.1:9050") == "socks5://127.0.0.1:9050"
    assert validate_proxy_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    assert validate_proxy_url("") == ""
    with pytest.raises(ValueError):
        validate_proxy_url("ftp://127.0.0.1:21")
    with pytest.raises(ValueError):
        validate_proxy_url("socks5://127.0.0.1:9050/secret")


def test_stale_v1_ack_does_not_count(isolated_risk_ack):
    isolated_risk_ack.write_text(
        json.dumps(
            {
                "notice_version": 1,
                "acknowledged": True,
                "authorized_use": True,
                "capabilities": {"tls_impersonate": True},
                "proxy_url": "socks5://127.0.0.1:9050",
            }
        ),
        encoding="utf-8",
    )
    status = get_status()
    assert status["acknowledged"] is False
    assert is_enabled("tls_impersonate") is False


def test_stale_v2_ack_does_not_count(isolated_risk_ack):
    isolated_risk_ack.write_text(
        json.dumps(
            {
                "notice_version": 2,
                "acknowledged": True,
                "authorized_use": True,
                "capabilities": {"argos_veil": True, "argos_conduit": True},
                "proxy_url": "",
            }
        ),
        encoding="utf-8",
    )
    status = get_status()
    assert status["acknowledged"] is False
    assert is_armed("argos_veil") is False
    assert is_enabled("argos_veil") is False


def test_veil_requires_proxy_or_conduit():
    denied = acknowledge(
        "I ACCEPT THE RISK",
        authorized_use=True,
        capabilities={"argos_veil": True},
    )
    assert denied["ok"] is False
    ok = acknowledge(
        "I ACCEPT THE RISK",
        authorized_use=True,
        capabilities={"argos_conduit": True, "argos_veil": True},
    )
    assert ok["ok"] is True
    assert is_armed("argos_veil") is True
    assert is_enabled("argos_veil") is False  # Conduit not listening yet
    assert is_enabled("argos_conduit") is True


def test_clearing_proxy_while_egress_on_fails():
    acknowledge(
        "I ACCEPT THE RISK",
        authorized_use=True,
        capabilities={"linkedin_public_fetch": True},
        proxy_url="socks5://127.0.0.1:9050",
    )
    assert is_enabled("linkedin_public_fetch") is True
    denied = update_capabilities({"linkedin_public_fetch": True}, proxy_url="")
    assert denied["ok"] is False
    assert is_enabled("linkedin_public_fetch") is True
    with pytest.raises(RiskCapabilityOff):
        require_capability("authorized_surface_enum")
