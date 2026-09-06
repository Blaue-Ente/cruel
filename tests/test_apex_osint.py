from __future__ import annotations

from app.apex.planner import heuristic_plan
from app.config import ADMIN_SECRET, DEFAULT_ADMIN_SECRET, admin_secret_is_insecure
from app.osint.techstack import detect_tech_stack
from app.playbook import get_playbook
from app.providers import classify_task
from app.recon.fallback import discover_feeds


def test_health_reports_v8_and_secure_admin(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"].startswith("8.")
    assert set(body["risk"]) == {"acknowledged", "any_enabled"}
    assert body["risk"]["acknowledged"] is False
    assert body["security"]["ssrf_protection"] is True
    assert body["security"]["websocket_requires_api_key"] is True
    assert body["security"]["admin_secret_insecure"] is False
    assert body["security"]["admin_secret_source"] in {"environment", "generated_file", "ephemeral"}
    assert "ADMIN_SECRET" not in str(body)
    assert "X-Request-Id" in r.headers


def test_admin_secret_not_shipped_default():
    assert ADMIN_SECRET != DEFAULT_ADMIN_SECRET
    assert admin_secret_is_insecure() is False


def test_bootstrap_generates_file(tmp_path, monkeypatch):
    from app.config import _bootstrap_admin_secret, DEFAULT_ADMIN_SECRET as shipped

    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    monkeypatch.setattr("app.config.ADMIN_SECRET_FILE", tmp_path / ".admin_secret")
    secret, source = _bootstrap_admin_secret()
    assert secret != shipped
    assert source == "generated_file"
    assert (tmp_path / ".admin_secret").read_text().strip() == secret


def test_classify_task_light_vs_reasoning():
    assert classify_task("extract") == "light"
    assert classify_task("entity") == "light"
    assert classify_task("dossier") == "reasoning"
    assert classify_task("apex") == "reasoning"
    assert classify_task("plan") == "reasoning"


def test_detect_tech_stack_wordpress_next():
    html = '<html><script src="/wp-content/x.js"></script><script id="__NEXT_DATA__"></script></html>'
    stack = detect_tech_stack(html, {"Server": "cloudflare", "x-powered-by": "Express"})
    names = {h["name"] for h in stack["technologies"]}
    assert "WordPress" in names
    assert "Next.js" in names
    assert "cloudflare" in names or "Cloudflare" in names
    assert "Express" in names


def test_discover_feeds_from_html():
    html = '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
    feeds = discover_feeds("https://example.com/blog", html)
    assert any(f.endswith("/feed.xml") for f in feeds)
    assert any("/rss.xml" in f for f in feeds)


def test_apex_heuristic_csuite():
    plan = heuristic_plan("Acme GmbH and its C-suite")
    assert "Acme" in plan["company"]
    tools = {s["tool"] for s in plan["steps"]}
    assert "corporate_intel" in tools
    assert "people_footprint" in tools
    assert plan["planner"] == "heuristic"


def test_apex_heuristic_domain():
    plan = heuristic_plan("https://example.com stock anomaly")
    assert "example.com" in plan["domains"] or plan["urls"]
    tools = {s["tool"] for s in plan["steps"]}
    assert "lawful_fallback" in tools
    assert "wayback" in tools


def test_playbook_covers_arsenal():
    book = get_playbook()
    ids = set(book["ids"])
    for key in (
        "apex",
        "swarm",
        "provocative_stock",
        "api_fuzz",
        "temporal",
        "ghost_cursor",
        "lawful_fallback",
        "byok",
        "risk_gate",
        "flaresolverr",
        "github_commit_emails",
    ):
        assert key in ids
    swarm = next(e for e in book["entries"] if e["id"] == "swarm")
    assert "authorized_target" in swarm["legal"]


def test_copilot_context_requires_key(client):
    r = client.get("/api/v1/copilot/context")
    assert r.status_code == 401


def test_playbook_public(client):
    r = client.get("/api/v1/playbook")
    assert r.status_code == 200
    assert "provocative_stock" in r.json()["ids"]


def test_rule_plan_apex():
    from app.copilot.engine import plan_with_rules

    plan = plan_with_rules("Apex dossier for Contoso and its C-suite", "standard", "DE")
    assert plan["tool_calls"][0]["name"] == "apex_run"


def test_rule_plan_context():
    from app.copilot.engine import plan_with_rules

    plan = plan_with_rules("Show runtime context and pheromones", "standard", "DE")
    assert plan["tool_calls"][0]["name"] == "inspect_context"


def test_graph_link_chain():
    from app.osint.graph import link_company_footprint, snapshot
    from app.store import init_db

    init_db()
    ids = link_company_footprint(
        "Contoso Ltd",
        domain="contoso.example",
        person="Ada Lovelace",
        role="Director",
        infrastructure=["ns1.example.net"],
        source="test",
    )
    assert ids.get("company")
    assert ids.get("person")
    snap = snapshot()
    rels = {e["rel"] for e in snap["edges"]}
    assert "operates_domain" in rels
    assert "holds_role" in rels
