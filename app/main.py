from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import require_admin, require_api_key
from app.config import BASE_DIR, SCRAPER_API_KEY
from app.llm import build_chat_reply, get_llm_status, parse_user_command
from app.models import (
    ApiKeyCreate,
    ApiKeyListItem,
    ApiKeyResponse,
    ChatRequest,
    ChatResponse,
    DashboardStats,
    LLMCommandJSON,
    ScrapeRequest,
    ScrapeResponse,
    UniversalScrapeBatchRequest,
    UniversalScrapeRequest,
)
from app.scraper import scrape_url
from app.store import (
    create_api_key,
    get_dashboard_stats,
    init_db,
    list_api_keys,
    log_scrape,
    revoke_api_key,
)
from app.universal_scraper import (
    get_scraper_capabilities,
    universal_scrape,
    universal_scrape_batch,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cruel Mini App",
    description="API keys, web scraping (Cruel + Scraper.io), and LLM admin",
    version="2.0.0",
    lifespan=lifespan,
)

static_dir = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    llm = get_llm_status()
    return {
        "status": "ok",
        "scraper_api_configured": bool(SCRAPER_API_KEY),
        "llm": llm,
        "scraperio": get_scraper_capabilities(),
    }


@app.get("/api/v1/dashboard", response_model=DashboardStats)
async def dashboard_stats():
    stats = get_dashboard_stats()
    return DashboardStats(
        total_api_keys=stats["total_api_keys"],
        active_api_keys=stats["active_api_keys"],
        total_scrapes=stats["total_scrapes"],
        scraper_api_configured=bool(SCRAPER_API_KEY),
        llm=get_llm_status(),
        scraperio=get_scraper_capabilities(),
    )


@app.get("/api/v1/llm/status")
async def llm_status():
    return get_llm_status()


# --- Admin: API Key Management ---


@app.post("/admin/keys", response_model=ApiKeyResponse, dependencies=[Depends(require_admin)])
async def admin_create_key(body: ApiKeyCreate):
    record = create_api_key(body.name, body.expires_days)
    return ApiKeyResponse(**record)


@app.get("/admin/keys", response_model=list[ApiKeyListItem], dependencies=[Depends(require_admin)])
async def admin_list_keys():
    return [ApiKeyListItem(**k) for k in list_api_keys()]


@app.delete("/admin/keys/{key_id}", dependencies=[Depends(require_admin)])
async def admin_revoke_key(key_id: str):
    if not revoke_api_key(key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": True, "id": key_id}


# --- API v1: Scrape & Chat ---


@app.post("/api/v1/scrape", response_model=ScrapeResponse)
async def api_scrape(body: ScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = scrape_url(body)
        log_scrape(str(body.url), "quick", items_count=1, success=True)
        return result
    except ValueError as e:
        log_scrape(str(body.url), "quick", success=False)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_scrape(str(body.url), "quick", success=False)
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")


@app.post("/api/v1/scrape/universal")
async def api_universal_scrape(body: UniversalScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = universal_scrape(
            url=str(body.url),
            author=body.author,
            content_type=body.content_type,
            max_items=body.max_items,
            production_mode=body.production_mode,
        )
        items_count = len(result.get("items", []))
        log_scrape(str(body.url), "universal", items_count=items_count, success=result.get("success", True))
        return result
    except Exception as e:
        log_scrape(str(body.url), "universal", success=False)
        raise HTTPException(status_code=502, detail=f"Universal scrape failed: {e}")


@app.post("/api/v1/scrape/universal/batch")
async def api_universal_scrape_batch(body: UniversalScrapeBatchRequest, _key: dict = Depends(require_api_key)):
    try:
        result = universal_scrape_batch(body.sources, max_items=body.max_items)
        for src in body.sources:
            log_scrape(src.get("url", "batch"), "universal_batch", items_count=len(result.get("items", [])))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Batch scrape failed: {e}")


@app.get("/api/v1/scrape/capabilities")
async def scrape_capabilities():
    return get_scraper_capabilities()


@app.post("/api/v1/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest, _key: dict = Depends(require_api_key)):
    command = parse_user_command(body.message, body.llm_provider, body.llm_model)
    scrape_result: Optional[ScrapeResponse] = None
    universal_result: Optional[dict[str, Any]] = None
    extra = None

    if command.intent.value == "admin":
        extra = "Admin actions require X-Admin-Secret header on /admin/keys endpoints."

    if body.execute_scrape and command.urls:
        try:
            if command.scrape_mode == "universal" or command.intent.value == "universal_scrape":
                universal_result = universal_scrape(command.urls[0])
                items = len(universal_result.get("items", []))
                log_scrape(command.urls[0], "universal", items_count=items)
                extra = f"Scraper.io OK — {items} items extracted"
            else:
                scrape_result = scrape_url(
                    ScrapeRequest(
                        url=command.urls[0],
                        extract=command.extract,
                        selectors=command.selectors or None,
                    )
                )
                log_scrape(command.urls[0], "quick", items_count=1)
                extra = f"Quick scrape OK — status {scrape_result.status_code}"
        except Exception as e:
            extra = f"Scrape failed: {e}"

    reply = build_chat_reply(command, extra)

    if body.json_only:
        return JSONResponse(content={
            "command": command.model_dump(),
            "scrape_result": scrape_result.model_dump() if scrape_result else None,
            "universal_result": universal_result,
        })

    return ChatResponse(reply=reply, command=command, scrape_result=scrape_result)


@app.post("/api/v1/parse", response_model=LLMCommandJSON)
async def api_parse(body: ChatRequest, _key: dict = Depends(require_api_key)):
    return parse_user_command(body.message, body.llm_provider, body.llm_model)


@app.post("/api/v1/chat/public", response_model=ChatResponse)
async def public_chat(body: ChatRequest):
    command = parse_user_command(body.message, body.llm_provider, body.llm_model)
    reply = build_chat_reply(command)
    if body.json_only:
        return JSONResponse(content={"command": command.model_dump()})
    return ChatResponse(reply=reply, command=command)
