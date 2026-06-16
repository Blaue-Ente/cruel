# Cruel Mini App v2

Мини приложение върху [Cruel](https://github.com/Bishwas-py/cruel) + интеграция с [Scraper.io](https://github.com/Aviral1303/Scraper.io).

## Възможности

| Модул | Описание |
|-------|----------|
| **Quick Scrape** | Cruel + BeautifulSoup — бързо извличане от една страница |
| **Universal Scrape** | Scraper.io — RSS, HTTP, blog, substack, PDF (4-tier fallback) |
| **NVIDIA NIM LLM** | Безплатни модели от build.nvidia.com (OpenAI-compatible) |
| **HuggingFace LLM** | Fallback inference API |
| **API ключове** | Генериране, списък, revoke |
| **Dashboard UI** | Пълен админ панел с sidebar навигация |

## Бърз старт

```bash
pip install -r requirements.txt
cp .env.example .env
# Задайте NVIDIA_API_KEY от https://build.nvidia.com
python3 run_app.py
```

Отворете http://localhost:8000

## Конфигурация

| Променлива | Описание |
|------------|----------|
| `NVIDIA_API_KEY` | NVIDIA NIM API ключ (препоръчано) |
| `NVIDIA_MODEL` | Модел (default: `meta/llama-3.1-8b-instruct`) |
| `HF_TOKEN` | Hugging Face токен (fallback) |
| `LLM_PROVIDER` | `auto` \| `nvidia` \| `huggingface` \| `rule` |
| `SCRAPER_API_KEY` | ScraperAPI proxy (опционално) |
| `ADMIN_SECRET` | Admin secret за API ключове |

### Безплатни NVIDIA модели

- `meta/llama-3.1-8b-instruct`
- `nvidia/nemotron-mini-4b-instruct`
- `meta/llama-3.2-3b-instruct`
- `microsoft/phi-3-mini-128k-instruct`
- `google/gemma-2-9b-it`

## API Endpoints

### Dashboard & Status

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/dashboard` | Статистики + LLM/Scraper.io статус |
| GET | `/api/v1/llm/status` | NVIDIA/HF provider info |
| GET | `/api/v1/scrape/capabilities` | Scraper.io стратегии |

### Scrape

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/scrape` | Quick scrape (Cruel) |
| POST | `/api/v1/scrape/universal` | Scraper.io universal scrape |
| POST | `/api/v1/scrape/universal/batch` | Batch universal scrape |

### Chat & LLM

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/chat` | NL команда + optional scrape |
| POST | `/api/v1/parse` | Pure JSON parsing |
| POST | `/api/v1/chat/public` | Demo без API ключ |

### Admin

| Метод | Endpoint | Auth |
|-------|----------|------|
| POST | `/admin/keys` | X-Admin-Secret |
| GET | `/admin/keys` | X-Admin-Secret |
| DELETE | `/admin/keys/{id}` | X-Admin-Secret |

## Примери

### NVIDIA LLM chat

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: cruel_..." \
  -H "Content-Type: application/json" \
  -d '{"message": "Universal scrape https://quill.co/blog", "execute_scrape": true, "llm_provider": "nvidia"}'
```

### Scraper.io universal scrape

```bash
curl -X POST http://localhost:8000/api/v1/scrape/universal \
  -H "X-API-Key: cruel_..." \
  -H "Content-Type: application/json" \
  -d '{"url": "https://quill.co/blog", "max_items": 10}'
```

### JSON output (Scraper.io format)

```json
{
  "team_id": "cruel-app",
  "items": [
    {
      "title": "Article Title",
      "content": "# Markdown content...",
      "content_type": "blog",
      "source_url": "https://...",
      "author": ""
    }
  ],
  "success": true
}
```

## Scraper.io интеграция

Интегриран е [Scraper.io UniversalScraper](https://github.com/Aviral1303/Scraper.io) с 4-tier fallback:

1. **RSS** — най-бърз за блогове
2. **HTTP + trafilatura** — статични страници
3. **Browser (Playwright)** — JS-heavy сайтове (опционално)
4. **Aggressive (Selenium)** — last resort (опционално)

За пълна функционалност:
```bash
pip install playwright selenium webdriver-manager
playwright install
```

## Архитектура

```
Dashboard UI
     │
     ▼
 FastAPI (app/)
 ├── Quick Scrape → cruel.session
 ├── Universal Scrape → app/scraperio/ (Scraper.io)
 ├── LLM Chat → NVIDIA NIM / HuggingFace / rule-based
 └── API Keys → SQLite
```

## Лиценз

GPL-3.0 (Cruel) · Scraper.io компоненти: MIT (оригинален repo)
