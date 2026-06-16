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

- [ ] Vision scraping (Playwright screenshot + NVIDIA vision model)
- [ ] Predictive pre-scraping (context-aware background research)
- [ ] StockArgos webhook integration
- [ ] Playwright stealth mode for Cloudflare bypass

## Лиценз

GPL-3.0 (Cruel) · Scraper.io: MIT
