# ArgosScout v8.2 — Autonomous OSINT & Deep Intelligence OS

Self-hosted research workstation: ask a question, get a **cited, compliance-aware dossier**. Copilot executes tools (Apex, search, extract, Wayback, registries, GDPR) instead of chatting in circles.

**North star:** time-to-trusted-insight — seconds from a prompt to sources you can defend.

## v8 Apex highlights

- **BYOK LLM hub** — OpenRouter (Claude / DeepSeek / Llama / Mistral / Gemini), OpenAI, Anthropic, Groq, NVIDIA, Hugging Face, local Ollama. Light tasks (routing, extract) go to fast/cheap models; dossiers and plans use reasoning models with fallback.
- **Apex Master Mode** — one target (`Company X and its C-suite`) → planner tree → cited forensic dossier, confidence, Person→Role→Company→Domain graph. Live Active Probe is never started from Apex.
- **Lawful fallback tree** — if live DOM is blocked: RSS/Atom, sitemap/JSON-LD, CDN hosts, RDAP, DNS TXT, Wayback, Common Crawl. Optional **operator risk gate** (off by default): BYO FlareSolverr, optional `curl_cffi` TLS impersonation, coherent WebGL/Audio profiles (no canvas noise), unauthenticated LinkedIn GET, GitHub public commit emails for a repo you name.
- **Corporate + people OSINT** — SEC EDGAR, Companies House, OpenCorporates, GitHub **public** org/user APIs, HTML tech-stack, careers-page signals, Wikipedia, news. LinkedIn is a **search URL** unless you accept the risk notice and enable public fetch. Commit-email harvest is the same opt-in, named repo only.
- **Feature Inspector** (`Ctrl+I`) — human playbook for Swarm Pheromones, Provocative Stock, API Fuzz, Temporal Spoofing, Ghost Cursor, privacy layers, Apex.
- **Dashboard** — status rings and provider pills instead of raw JSON dumps.
- **Admin secret hygiene** — shipped default is rejected. Empty `ADMIN_SECRET` generates `data/.admin_secret` (mode 0600). Health reports `admin_secret_source`, never the secret.
- **Operator risk gate** — Settings → read the EN/BG notice → confirm authorized use → type `I ACCEPT THE RISK` or `ПРИЕМАМ РИСКА` → enable each switch. Revoke turns everything off. ArgosScout does **not** ship a Cloudflare/Turnstile solver.
- **Dual-layer research** — Layer A Discovery fills an unverified Research Inbox. Layer B Verification is optional (`Verify selected` / entity / claim / entire) and never a single “truth score”.

## Dual-layer research

Discovery and Verification share Access Policy, Privacy Layers, SSRF, provenance, and budget envelopes. Verification is optional; security is not.

| Workflow | What happens |
|----------|----------------|
| Discover only | Public traces, registries, archives → Inbox. `verification_status=not_requested`. |
| Discover → Verify | Same, then an explicit second pass with its own budget. |

Search snippets are traces, not read sources. Republished copies count as one origin. People are not merged by name. Export keeps unverified status. `RESEARCH_LOCAL_ONLY=true` blocks cloud LLM comments during verification.

## Operator risk gate

All of the following are **off until you opt in**. Enabling them is your legal responsibility.

| Option | What it actually does | What it does not do |
|--------|----------------------|---------------------|
| FlareSolverr | POST to **your** instance (`FLARESOLVERR_URL`, default loopback `:8191`) | No bundled CF/Turnstile solver |
| TLS impersonate | Optional `curl_cffi` Chrome-like JA3 GET | Not a WAF exploit; still SSRF-gated |
| Fingerprint profiles | Align UA / platform / WebGL / AudioContext; hide `navigator.webdriver` | No canvas noise, not anti-detect-as-a-service |
| LinkedIn public fetch | Unauthenticated GET; login wall / 999 **fail closed** | No stealth login |
| GitHub commit emails | Public commits API for a **repo you name**, max 30 | No GitHub-wide person hunt |

```bash
# After acknowledging in Settings and enabling flaresolverr:
# docker run -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
FLARESOLVERR_URL=http://127.0.0.1:8191
# pip install curl_cffi   # only if you enable tls_impersonate
```

## v7 highlights (still in)

- **Command-first UI** — dashboard prompt, `Ctrl+K` palette, `Ctrl+J` copilot dock, themes, EN/BG, workspace export/import
- **Native copilot** — `research`, `scrape`, `wayback`, `seo_autopsy`, `detective`, `apex_run`, `corporate_intel`, `lawful_fallback`, `inspect_context`, `gdpr_scan`, `inspect_health`, `spot_anomalies`
- **Zero-trust outbound fetch** — SSRF guards (private IPs, metadata, credential URLs, redirect re-check)
- **Rate limits, request IDs, security headers**, WebSocket API key required
- **Live probe** requires `authorized_target=true` (no silent live fuzzing)
- **Observability** — activity log, anomaly suggestions, mode failure rates

## Безплатни AI алтернативи

| Provider | Скорост | Цена | Ключ |
|----------|---------|------|------|
| **Groq** | 800+ tok/s | Безплатен tier | console.groq.com |
| **NVIDIA NIM** | Бърз | Безплатни модели | build.nvidia.com |
| **HuggingFace** | Среден | Безплатен tier | huggingface.co |
| **Ollama** | Локален | 100% безплатен | ollama.com |
| **DuckDuckGo** | — | Без API ключ | вградено |
| **Wayback Machine** | — | Безплатен | archive.org |

Auto priority: **light** `Groq → OpenRouter → OpenAI → NVIDIA → Ollama` · **reasoning** `OpenRouter → Anthropic → OpenAI → Groq`


## Уникални функции

### ArgosScout Agent (автономно търсене)
```
Потребител: "Намери Prop Trading фирми за swing trading"
  → LLM генерира search queries
  → DuckDuckGo търсене (безплатно)
  → Паралелен scrape на топ резултати
  → Wayback Machine temporal анализ
  → LLM синтезира отговор
```

### WebSocket Live Stream
```javascript
ws = new WebSocket("ws://localhost:8000/ws/agent")
ws.send(JSON.stringify({ goal: "...", api_key: "cruel_..." }))
// → thought events в реално време
```

### Self-Healing Selectors
Ако CSS селекторите се счупят, LLM анализира DOM и предлага нови:
```
POST /api/v1/scrape/self-heal
{"url": "https://...", "selectors": {"price": ".old-price"}}
```

### Temporal Data (Wayback Machine)
```
POST /api/v1/wayback
{"url": "https://firm.com/rules"}
→ "Страницата е променена преди 2 месеца, съдържанието е нараснало с 12KB"
```

### Semantic DOM Filtering
Автоматично премахва реклами, cookie банери, навигация (trafilatura + readability).

### Vision Scraping (v3.1)
Playwright screenshot → Vision LLM (NVIDIA / Groq free). Чете страницата като човек.
```bash
POST /api/v1/scrape/vision
{"url": "https://example.com", "goal": "extract prices and titles"}
```
Fallback без Playwright: semantic HTML + LLM.

### Predictive Pre-Scraping (v3.1)
Следи контекста на работата и в бекграунд scrape-ва релевантно съдържание.
```bash
POST /api/v1/predictive/context   # записва интерес
GET  /api/v1/predictive/suggestions?message=...
POST /api/v1/predictive/run       # ръчен цикъл
```
Автоматичен бекграунд цикъл на всеки 300s (конфигурируем).

## Active Probe (v4.0) — Активен Изследовател

| Режим | Описание |
|-------|----------|
| `provocative_stock` | Добавя 9999 в количката → прихваща грешка с наличности |
| `provocative_form` | Extreme form values → validation errors |
| `conversational` | LLM генерира запитване → попълва форми/чат (dry_run по подразбиране) |
| `api_fuzz` | Shadow map на API endpoints + LLM path guessing |
| `temporal` | Date() spoofing за time-gated съдържание |
| `vision` | Screenshot + Vision LLM |
| `swarm` | Паралелни micro-scrapers с pheromone памет |

```bash
POST /api/v1/probe/run
{
  "url": "https://shop.example.com/product",
  "modes": ["provocative_stock", "api_fuzz", "swarm"],
  "goal": "stock levels and pricing",
  "dry_run": true
}

GET /api/v1/probe/pheromones   # sweet/poison routing memory
```

**Pheromones:** Sweet = добър източник, Poison = CAPTCHA/block → swarm избягва. v5: Redis primary, SQLite fallback.

## Privacy Layers (Слоеве на поверителност) — v6.0

Risk-based compliance: различни инструменти според юрисдикцията и риска.

| Layer | Код | Описание |
|-------|-----|----------|
| 👻 Ghost | `ghost` | Пасивен: Common Crawl, Wayback, JSON-LD — нулев live риск |
| Standard | `standard` | Глобален: API echo + SEO + scrape, лек PII филтър |
| 🇪🇺 EU Shield | `eu_shield` | Пълен GDPR, robots.txt, probe само dry_run |
| 🇩🇪 DE Fortress | `de_fortress` | Германия: най-строг GDPR, маскиране на лични имейли |
| 🎯 Hunter | `hunter` | Агресивен (ROW): пълен probe arsenal |

Auto-resolve: `DE` → de_fortress · EU → eu_shield · US → standard

```bash
# Smart Detective pipeline (layer-aware)
POST /api/v1/intelligence/detective
{"url": "https://...", "privacy_layer": "de_fortress", "country": "DE"}

# SEO Autopsy — JSON-LD, OpenGraph, Sitemap
POST /api/v1/scrape/seo-autopsy
{"url": "https://course-site.com"}

# API Echo — official APIs first
POST /api/v1/scrape/api-echo
{"url": "https://github.com/org/repo"}

# Common Crawl — passive archive
POST /api/v1/passive/common-crawl
{"url": "https://example.com", "keyword": "pricing"}

# OSINT + Trust Score
POST /api/v1/osint/investigate
{"name": "...", "tiktok_url": "...", "country": "DE", "privacy_layer": "de_fortress"}

# GDPR scan
POST /api/v1/compliance/gdpr-scan
{"text": "...", "privacy_layer": "de_fortress"}

GET /api/v1/compliance/layers
```

## v5.0 — Multimodal + Inbox + StockArgos

| Функция | Описание |
|---------|----------|
| **TikTok Multimodal** | Vision frames + audio tone + LLM synthesis |
| **Inbox IMAP** | Реални имейл отговори от conversational probe forms |
| **Redis Pheromones** | Бърза pheromone памет (auto fallback към SQLite) |
| **StockArgos Webhook** | EES score + signal delivery към StockArgos |

```bash
# TikTok multimodal analysis
POST /api/v1/multimodal/tiktok
{"url": "https://www.tiktok.com/@user/video/123"}

# Inbox — form submission tracking + IMAP poll
POST /api/v1/inbox/poll
GET  /api/v1/inbox/submissions
GET  /api/v1/inbox/messages

# StockArgos signals
POST /api/v1/integrations/stockargos/signal
GET  /api/v1/integrations/stockargos/signals

# Probe with StockArgos emit
POST /api/v1/probe/run
{"url": "...", "modes": ["api_fuzz"], "emit_stockargos": true}
```

```bash
pip install playwright redis
python3 -m playwright install chromium
```

## API Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /api/v1/apex/run` | Apex Master Mode — cited public-source dossier |
| `GET /api/v1/apex/last` | Last Apex dossier |
| `POST /api/v1/osint/corporate` | SEC / Companies House / OpenCorporates / GitHub org |
| `GET /api/v1/osint/graph` | Knowledge-graph snapshot |
| `POST /api/v1/recon/fallback` | Lawful fallback tree |
| `GET /api/v1/compliance/risk` | Operator notice (public) |
| `GET /api/v1/compliance/risk/status` | Acknowledgment + capability flags |
| `POST /api/v1/compliance/risk/acknowledge` | Phrase + `authorized_use` |
| `POST /api/v1/compliance/risk/capabilities` | Per-option switches |
| `POST /api/v1/compliance/risk/revoke` | Clear acknowledgment |
| `POST /api/v1/recon/flaresolverr` | BYO FlareSolverr (403 until enabled) |
| `POST /api/v1/osint/linkedin` | Unauthenticated LinkedIn GET (403 until enabled) |
| `POST /api/v1/osint/github-emails` | Public commit author emails (403 until enabled) |
| `GET /api/v1/playbook` | Feature Inspector catalog |
| `GET /api/v1/copilot/context` | Scan / pheromone / obstacle context |
| `POST /api/v1/copilot` | Action copilot (tools + synthesis) |
| `GET /api/v1/copilot/suggestions` | Proactive optimizations from logs/config |
| `GET/PUT /api/v1/preferences` | Workspace preferences |
| `GET /api/v1/workspace/export` | Export preferences JSON |
| `POST /api/v1/workspace/import` | Import preferences JSON |
| `GET /api/v1/observability/activity` | Recent jobs |
| `POST /api/v1/agent/research` | Автономно търсене + синтез |
| `WS /ws/agent` | Live thought stream (API key required) |
| `POST /api/v1/wayback` | Wayback temporal анализ |
| `POST /api/v1/scrape/self-heal` | Self-healing selectors |
| `POST /api/v1/scrape` | Quick scrape (Cruel) |
| `POST /api/v1/scrape/universal` | Scraper.io deep scrape |
| `POST /api/v1/chat` | LLM чатбот |

## Стартиране

```bash
pip install -r requirements.txt
cp .env.example .env
# GROQ_API_KEY=gsk_...  (препоръчано)
python3 run_app.py
```

## Deploy

**Railway is the supported host** (long-running uvicorn, writable disk, optional volume at `/data`). Bind address is `0.0.0.0` and the listen port is `PORT` (Railway) or `APP_PORT` (local). Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set `DATA_DIR=/data` when a volume is mounted so SQLite and the generated admin secret survive redeploys. `INBOX_ENABLED` stays off unless IMAP is configured.

**Vercel** auto-detects FastAPI at `app/main.py` and runs it as a Function. That is enough for a dashboard probe, with caveats:

- The app filesystem is read-only. Data, SQLite, and the generated admin secret go to `/tmp/argoscout-data` and vanish on cold start.
- Background predictive and IMAP loops do not start (`VERCEL=1`).
- Live probe / Playwright browsers are not a fit on the Function.

A previous production crash (`FUNCTION_INVOCATION_FAILED` on `cruel-omega.vercel.app`) was the app calling `mkdir` on `data/` during import. Boot now falls back to `/tmp` instead of dying.

## Бъдещи интеграции (Argos Ecosystem)

| Проект | ArgosScout роля |
|--------|-----------------|
| **StockArgos** | Market signal scraping + EES index |
| **ArgosWard** | Security policy monitoring |
| **VaultTreasury** | Financial data extraction |
| **ArgosAssistant** | Voice/chat interface |

## Roadmap

- [x] Vision scraping (Playwright + NVIDIA/Groq vision, HTML fallback)
- [x] Predictive pre-scraping (context-aware background research)
- [x] Active Probe v4 (provocative, conversational, swarm, pheromones)
- [x] TikTok multimodal (vision + audio tone analysis)
- [x] IMAP inbox integration (real email form responses)
- [x] Redis pheromones (SQLite fallback)
- [x] StockArgos webhook integration
- [x] Privacy Layers (ghost/standard/eu_shield/de_fortress/hunter)
- [x] SEO Autopsy (JSON-LD, OpenGraph, Sitemap)
- [x] API Echo (GitHub, Reddit, HN + discovery)
- [x] Common Crawl passive scraping
- [x] OSINT Synthesis + Trust Score
- [x] GDPR Anonymizer gate
- [x] Native action copilot + command-first UI
- [x] SSRF / rate-limit / request-id / WS auth
- [x] Workspace preferences export/import
- [x] BYOK LLM hub (OpenRouter / OpenAI / Anthropic) + light vs reasoning routing
- [x] Apex Master Mode + knowledge graph
- [x] Lawful fallback tree (RSS, RDAP, Wayback, Common Crawl)
- [x] Feature Inspector playbook
- [x] Generated admin secret (no shipped default)
- [x] Operator risk gate (opt-in FlareSolverr / TLS impersonate / fingerprints / LinkedIn / GitHub emails)
- [x] Dual-layer Discovery Inbox + optional Verification Center
- [ ] Optional allow-list of scrape hosts for locked-down deployments

**Not shipped as always-on (by design):** Cloudflare challenge bypass, canvas-noise anti-detect, LinkedIn login bypass, GitHub-wide email harvesting. Those exist only behind the operator risk gate, off by default.

## Лиценз

GPL-3.0 (Cruel) · Scraper.io: MIT
