"""In-app Feature Inspector / arsenal playbook.

Human-readable explanations, use-cases, expected outputs, and legal notes.
This is documentation served to the UI — not an execution surface.
"""

from __future__ import annotations

from typing import Any, Optional

ENTRIES: list[dict[str, Any]] = [
    {
        "id": "apex",
        "name": "Apex Master Mode",
        "category": "orchestration",
        "summary": "One prompt → planner tree → public-source dossier with citations, confidence, and a relationship graph.",
        "use_when": "You have a company, domain, or 'Company X and its C-suite' style question and want a cited pack, not a scrape dump.",
        "expected": "Headline, executive summary, key findings with citation ids, gaps, Person→Company→Domain graph.",
        "legal": "Public registries, RSS, archives, and documented APIs only. Live Active Probe is never started from Apex.",
        "outputs": ["dossier", "citations", "knowledge graph"],
    },
    {
        "id": "quick_scrape",
        "name": "Quick Scrape",
        "category": "extract",
        "summary": "Single-page HTTP extract of title, text, links, and meta via Cruel + BeautifulSoup.",
        "use_when": "You already have a public URL and need the visible text fast.",
        "expected": "Extracted fields plus a short text preview.",
        "legal": "SSRF-guarded public http(s) only. Respect robots and privacy layer. Do not point at hosts you may not fetch.",
        "outputs": ["title", "text", "links", "meta"],
    },
    {
        "id": "universal",
        "name": "Universal Scrape",
        "category": "extract",
        "summary": "Scraper.io fallback ladder: RSS → HTTP → optional browser → aggressive HTML.",
        "use_when": "Blogs, feeds, or multi-article sources.",
        "expected": "A list of items (title, url, content) from the first strategy that works.",
        "legal": "Same as Quick Scrape. Browser tier is identity-consistent UA/viewport, not a challenge bypass.",
        "outputs": ["items", "strategy"],
    },
    {
        "id": "detective",
        "name": "Smart Detective",
        "category": "intelligence",
        "summary": "Layer-aware pipeline: API Echo → SEO Autopsy → Common Crawl → Wayback → semantic extract, then lawful fallback if live DOM fails.",
        "use_when": "A site may block scrapers, or you want structured data the page already publishes.",
        "expected": "winning_method, findings per stage, GDPR summary.",
        "legal": "Follows the selected privacy layer. Ghost stays on archives. No login-wall bypass.",
        "outputs": ["winning_method", "findings", "gdpr"],
    },
    {
        "id": "lawful_fallback",
        "name": "Lawful fallback tree",
        "category": "intelligence",
        "summary": "When live DOM is blocked: RSS/Atom, sitemap/JSON-LD, CDN hosts, RDAP, DNS TXT, Wayback, Common Crawl.",
        "use_when": "403/captcha/empty page — you still need public evidence.",
        "expected": "winning_method plus per-method findings.",
        "legal": "Passive public sources only. ArgosScout does not spoof TLS/JA3, canvas, or solve challenges.",
        "outputs": ["rss", "rdap", "wayback", "common_crawl"],
    },
    {
        "id": "swarm",
        "name": "Swarm Pheromones",
        "category": "probe",
        "summary": "Parallel micro-fetchers that remember sweet (useful) and poison (blocked) URL patterns in Redis or SQLite.",
        "use_when": "Authorized mapping of a site you operate, so later jobs skip dead ends.",
        "expected": "Per-worker notes and a pheromone log.",
        "legal": "Part of Active Probe. Live runs require authorized_target=true. Default is dry_run.",
        "outputs": ["pheromones", "worker results"],
    },
    {
        "id": "provocative_stock",
        "name": "Provocative Stock",
        "category": "probe",
        "summary": "On a shop you are allowed to test, submit an extreme cart quantity to read stock/validation errors the UI already returns.",
        "use_when": "You own the storefront and need availability signals that the product page hides.",
        "expected": "Request/response notes in dry_run; live only with authorization.",
        "legal": "Authorized testing only. Not for inventory theft against third parties. Prefer dry_run.",
        "outputs": ["validation_errors", "hints"],
    },
    {
        "id": "api_fuzz",
        "name": "API Fuzz",
        "category": "probe",
        "summary": "Shadow-map of same-origin paths the HTML already references, plus conservative path guesses.",
        "use_when": "Documenting your own app's public API surface.",
        "expected": "Candidate URLs and status codes. Not an exploit framework.",
        "legal": "No payload exploits, no auth bypass. Live requires authorized_target=true.",
        "outputs": ["candidates", "statuses"],
    },
    {
        "id": "temporal",
        "name": "Temporal Spoofing",
        "category": "probe",
        "summary": "Shift the browser clock for pages that gate content on Date() (countdown, embargo).",
        "use_when": "Authorized review of time-gated UX on a property you control.",
        "expected": "Before/after notes of visible content.",
        "legal": "Does not forge server-side sessions or TLS. Authorized hosts only.",
        "outputs": ["visible_delta"],
    },
    {
        "id": "ghost_cursor",
        "name": "Ghost Cursor",
        "category": "browser",
        "summary": "Bezier mouse paths, variable typing cadence, scroll pauses, and tiny viewport nudges during authorized Playwright sessions.",
        "use_when": "Vision scrape on a site that expects a real viewport — not to defeat bot management.",
        "expected": "More complete screenshots on ordinary pages.",
        "legal": "Human-like cadence for pages you may browse. Not fingerprint spoofing (no canvas/WebGL/JA3 noise).",
        "outputs": ["screenshot"],
    },
    {
        "id": "privacy_layers",
        "name": "Privacy Layers",
        "category": "compliance",
        "summary": "ghost / standard / eu_shield / de_fortress / hunter — which methods are allowed and how PII is gated.",
        "use_when": "Research that must stay GDPR-aware or archive-only.",
        "expected": "Policy profile, allowed methods, GDPR mask counts.",
        "legal": "de_fortress and eu_shield tighten live collection and mask personal emails. Hunter is for ROW authorized research.",
        "outputs": ["layer", "allowed_methods"],
    },
    {
        "id": "corporate",
        "name": "Corporate intelligence",
        "category": "osint",
        "summary": "SEC EDGAR search, Companies House (API or search URL), OpenCorporates, GitHub public org metadata, careers-page signals, HTML tech-stack.",
        "use_when": "Company due diligence from public registries.",
        "expected": "Filings/search URLs, stack signatures, hiring page hits.",
        "legal": "Public APIs and search URLs. No Handelsregister paid scrape, no login walls.",
        "outputs": ["registries", "stack", "hiring"],
    },
    {
        "id": "people",
        "name": "People footprint",
        "category": "osint",
        "summary": "Wikipedia summary, GitHub public user, news search, LinkedIn search URL.",
        "use_when": "Public professional context for a named person already in the news or Wikipedia.",
        "expected": "Public snippets and search links — not a dossier of private emails.",
        "legal": "No LinkedIn scraping, no GitHub commit-email harvesting, no stalking of private individuals.",
        "outputs": ["wikipedia", "github", "news", "linkedin_search"],
    },
    {
        "id": "byok",
        "name": "BYOK LLM hub",
        "category": "system",
        "summary": "Bring OpenRouter, OpenAI, Anthropic, Groq, NVIDIA, Hugging Face, or local Ollama. Light tasks go to fast/cheap models; dossiers use reasoning models.",
        "use_when": "You want Claude/DeepSeek/Llama without locking to NVIDIA/Groq.",
        "expected": "Health routing shows light vs reasoning provider:model chains.",
        "legal": "Keys stay on your host. Never paste secrets into Copilot chat.",
        "outputs": ["routing.light", "routing.reasoning"],
    },
]


def get_playbook() -> dict[str, Any]:
    return {
        "title": "ArgosScout Feature Inspector",
        "stance": (
            "ArgosScout is a privacy-first research OS. It does not implement Cloudflare "
            "challenge solvers, JA3/canvas spoofing, or credential stuffing. When a live "
            "page refuses inspection, use the lawful fallback tree."
        ),
        "entries": ENTRIES,
        "ids": [e["id"] for e in ENTRIES],
    }


def get_entry(entry_id: str) -> Optional[dict[str, Any]]:
    for item in ENTRIES:
        if item["id"] == entry_id:
            return item
    return None
