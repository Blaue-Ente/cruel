# ArgosScout v3 — Autonomous Knowledge Agent

Еволюция от Cruel Mini App → **ArgosScout** — автономен агент за знание, интегриран с Argos екосистемата.

## Безплатни AI алтернативи

| Provider | Скорост | Цена | Ключ |
|----------|---------|------|------|
| **Groq** | 800+ tok/s | Безплатен tier | console.groq.com |
| **NVIDIA NIM** | Бърз | Безплатни модели | build.nvidia.com |
| **HuggingFace** | Среден | Безплатен tier | huggingface.co |
| **Ollama** | Локален | 100% безплатен | ollama.com |
| **DuckDuckGo** | — | Без API ключ | вградено |
| **Wayback Machine** | — | Безплатен | archive.org |

Auto priority: `Groq → NVIDIA → HuggingFace → Ollama → rule-based`

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

**Pheromones:** Sweet = добър източник, Poison = CAPTCHA/block → swarm избягва.

## API Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /api/v1/agent/research` | Автономно търсене + синтез |
| `WS /ws/agent` | Live thought stream |
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
- [ ] StockArgos webhook integration
- [ ] Playwright stealth mode for Cloudflare bypass

## Лиценз

GPL-3.0 (Cruel) · Scraper.io: MIT
