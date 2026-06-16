# Cruel Mini App

Мини приложение върху [Cruel](https://github.com/Bishwas-py/cruel) — Python библиотека за web scraping. Добавя:

- **API ключове** — генериране и управление на потребителски ключове
- **REST API за scrape** — структуриран JSON изход (title, text, links, meta, custom selectors)
- **LLM чатбот администратор** — разбира команди на български/английски и връща структуриран JSON
- **Web UI** — админ панел + чат интерфейс

## Бърз старт

```bash
pip install -r requirements.txt
cp .env.example .env   # настройте SCRAPER_API_KEY, HF_TOKEN, ADMIN_SECRET
python3 run_app.py
```

Отворете http://localhost:8000

## Конфигурация

| Променлива | Описание |
|------------|----------|
| `SCRAPER_API_KEY` | ScraperAPI ключ (опционално — без него се ползва директен fetch) |
| `HF_TOKEN` | Hugging Face токен за безплатен LLM (опционално — fallback rule-based parser) |
| `LLM_MODEL` | HF модел (по подразбиране: `HuggingFaceH4/zephyr-7b-beta`) |
| `ADMIN_SECRET` | Секрет за управление на API ключове |

## API Endpoints

### Admin (изисква `X-Admin-Secret`)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/admin/keys` | Генерира нов API ключ |
| GET | `/admin/keys` | Списък с ключове |
| DELETE | `/admin/keys/{id}` | Отнема ключ |

### API v1 (изисква `X-API-Key`)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/scrape` | Scrape URL → JSON |
| POST | `/api/v1/chat` | NL команда → отговор + JSON command |
| POST | `/api/v1/parse` | Само JSON parsing (за LLM-to-LLM) |

### Публичен demo

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/chat/public` | Чат без API ключ (без scrape) |

## Примери

### Генериране на API ключ

```bash
curl -X POST http://localhost:8000/admin/keys \
  -H "X-Admin-Secret: cruel-admin-change-me" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app"}'
```

### Scrape

```bash
curl -X POST http://localhost:8000/api/v1/scrape \
  -H "X-API-Key: cruel_..." \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "extract": ["title", "text", "links"]}'
```

### LLM чат (JSON режим)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: cruel_..." \
  -H "Content-Type: application/json" \
  -d '{"message": "Кои сайтове за имоти в България?", "json_only": true}'
```

### Директен JSON parse (за друг LLM)

```bash
curl -X POST http://localhost:8000/api/v1/parse \
  -H "X-API-Key: cruel_..." \
  -H "Content-Type: application/json" \
  -d '{"message": "Scrape https://www.fiverr.com/user/gig-slug"}'
```

## LLM JSON Schema

Чатботът връща структуриран обект за бърза комуникация с други LLM агенти:

```json
{
  "intent": "scrape | search_sites | admin | help | chat",
  "urls": ["https://..."],
  "selectors": {"price": ".price-tag"},
  "extract": ["title", "text", "links", "meta"],
  "query": "оригинално съобщение",
  "explanation": "обяснение",
  "confidence": 0.85,
  "suggested_sites": [{"name": "...", "url": "...", "note": "..."}],
  "admin_action": null
}
```

## Архитектура

```
Client / LLM Agent
       │
       ▼
  FastAPI (app/)
  ├── /admin/keys     → SQLite (API keys)
  ├── /api/v1/scrape  → cruel.session → ScraperAPI (optional)
  ├── /api/v1/chat    → HF Inference LLM → JSON command
  └── /api/v1/parse   → pure JSON for LLM-to-LLM
```

## Оригинална Cruel библиотека

`cruel` остава непроменена — pip пакет за scraping с BeautifulSoup + ScraperAPI.

```python
from cruel import session
session.set_scraper_api_key("YOUR_KEY")
response = session.get("https://example.com")
print(response.soup)
```

## Лиценз

GPL-3.0 (наследен от Cruel)
