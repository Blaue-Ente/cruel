from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import require_admin, require_api_key
from app.config import BASE_DIR, SCRAPER_API_KEY
from app.llm import build_chat_reply, parse_user_command
from app.models import (
    ApiKeyCreate,
    ApiKeyListItem,
    ApiKeyResponse,
    ChatRequest,
    ChatResponse,
    LLMCommandJSON,
    ScrapeRequest,
    ScrapeResponse,
)
from app.scraper import scrape_url
from app.store import create_api_key, init_db, list_api_keys, revoke_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cruel Mini App",
    description="API keys, web scraping, and LLM-powered admin chatbot",
    version="1.0.0",
    lifespan=lifespan,
)

static_dir = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "scraper_api_configured": bool(SCRAPER_API_KEY),
        "llm_available": True,
    }


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
        return scrape_url(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")


@app.post("/api/v1/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest, _key: dict = Depends(require_api_key)):
    command = parse_user_command(body.message)
    scrape_result: Optional[ScrapeResponse] = None
    extra = None

    if command.intent.value == "admin":
        extra = "Admin actions require X-Admin-Secret header on /admin/keys endpoints."

    if body.execute_scrape and command.urls:
        try:
            scrape_result = scrape_url(
                ScrapeRequest(url=command.urls[0], extract=command.extract, selectors=command.selectors or None)
            )
            extra = f"Scrape OK — status {scrape_result.status_code}"
        except Exception as e:
            extra = f"Scrape failed: {e}"

    reply = build_chat_reply(command, extra)

    if body.json_only:
        return JSONResponse(content={
            "command": command.model_dump(),
            "scrape_result": scrape_result.model_dump() if scrape_result else None,
        })

    return ChatResponse(reply=reply, command=command, scrape_result=scrape_result)


@app.post("/api/v1/parse", response_model=LLMCommandJSON)
async def api_parse(body: ChatRequest, _key: dict = Depends(require_api_key)):
    """Pure JSON command parsing for LLM-to-LLM communication."""
    return parse_user_command(body.message)


# --- Convenience: chat without scrape execution for UI ---


@app.post("/api/v1/chat/public", response_model=ChatResponse)
async def public_chat(body: ChatRequest):
    """Demo chat endpoint (no API key). Does not execute scrapes."""
    command = parse_user_command(body.message)
    reply = build_chat_reply(command)
    if body.json_only:
        return JSONResponse(content={"command": command.model_dump()})
    return ChatResponse(reply=reply, command=command)
