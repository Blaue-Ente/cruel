import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent import run_agent, stream_agent_thoughts
from app.auth import require_admin, require_api_key
from app.config import APP_NAME, BASE_DIR, SCRAPER_API_KEY
from app.llm import build_chat_reply, get_llm_status, parse_user_command
from app.models import (
    AgentRequest,
    AgentResponse,
    ApiKeyCreate,
    ApiKeyListItem,
    ApiKeyResponse,
    ChatRequest,
    ChatResponse,
    DashboardStats,
    LLMCommandJSON,
    ScrapeRequest,
    ScrapeResponse,
    SelfHealRequest,
    UniversalScrapeBatchRequest,
    UniversalScrapeRequest,
    WaybackRequest,
)
from app.scraper import scrape_url
from app.self_heal import extract_with_healing
from app.store import (
    create_api_key,
    get_dashboard_stats,
    init_db,
    list_api_keys,
    log_scrape,
    revoke_api_key,
    validate_api_key,
)
from app.universal_scraper import (
    get_scraper_capabilities,
    universal_scrape,
    universal_scrape_batch,
)
from app.wayback import temporal_analysis

import requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=APP_NAME,
    description="ArgosScout — Autonomous Knowledge Agent (Cruel + Scraper.io)",
    version="3.0.0",
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
        "app": APP_NAME,
        "scraper_api_configured": bool(SCRAPER_API_KEY),
        "llm": get_llm_status(),
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


# --- Admin ---


@app.post("/admin/keys", response_model=ApiKeyResponse, dependencies=[Depends(require_admin)])
async def admin_create_key(body: ApiKeyCreate):
    return ApiKeyResponse(**create_api_key(body.name, body.expires_days))


@app.get("/admin/keys", response_model=list[ApiKeyListItem], dependencies=[Depends(require_admin)])
async def admin_list_keys():
    return [ApiKeyListItem(**k) for k in list_api_keys()]


@app.delete("/admin/keys/{key_id}", dependencies=[Depends(require_admin)])
async def admin_revoke_key(key_id: str):
    if not revoke_api_key(key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": True, "id": key_id}


# --- Scrape ---


@app.post("/api/v1/scrape", response_model=ScrapeResponse)
async def api_scrape(body: ScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = scrape_url(body)
        log_scrape(str(body.url), "quick", items_count=1, success=True)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")


@app.post("/api/v1/scrape/universal")
async def api_universal_scrape(body: UniversalScrapeRequest, _key: dict = Depends(require_api_key)):
    try:
        result = universal_scrape(
            url=str(body.url), author=body.author,
            content_type=body.content_type, max_items=body.max_items,
            production_mode=body.production_mode,
        )
        log_scrape(str(body.url), "universal", items_count=len(result.get("items", [])), success=result.get("success", True))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Universal scrape failed: {e}")


@app.post("/api/v1/scrape/universal/batch")
async def api_universal_scrape_batch(body: UniversalScrapeBatchRequest, _key: dict = Depends(require_api_key)):
    try:
        return universal_scrape_batch(body.sources, max_items=body.max_items)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Batch scrape failed: {e}")


@app.get("/api/v1/scrape/capabilities")
async def scrape_capabilities():
    return get_scraper_capabilities()


@app.post("/api/v1/scrape/self-heal")
async def api_self_heal(body: SelfHealRequest, _key: dict = Depends(require_api_key)):
    try:
        resp = requests.get(str(body.url), timeout=15, headers={"User-Agent": "ArgosScout/1.0"})
        result = extract_with_healing(resp.text, body.selectors, str(body.url))
        return {"url": str(body.url), "extracted": result, "status_code": resp.status_code}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/v1/wayback")
async def api_wayback(body: WaybackRequest, _key: dict = Depends(require_api_key)):
    return temporal_analysis(str(body.url))


# --- ArgosScout Agent ---


@app.post("/api/v1/agent/research", response_model=AgentResponse)
async def api_agent_research(body: AgentRequest, _key: dict = Depends(require_api_key)):
    result = await run_agent(
        body.goal, provider=body.llm_provider, model=body.llm_model,
        use_wayback=body.use_wayback, deep_scrape=body.deep_scrape,
    )
    log_scrape(body.goal[:100], "agent", items_count=result.get("sources_scraped", 0))
    if result.get("status") == "clarification_needed":
        return AgentResponse(status="clarification_needed", goal=body.goal, question=result.get("question"))
    return AgentResponse(
        status=result["status"], goal=result["goal"],
        synthesis=result.get("synthesis"),
        search_queries=result.get("search_queries", []),
        sources_found=result.get("sources_found", 0),
        sources_scraped=result.get("sources_scraped", 0),
        search_results=result.get("search_results", []),
        scraped=result.get("scraped", []),
        wayback=result.get("wayback", []),
    )


@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        api_key = payload.get("api_key", "")
        if api_key and not validate_api_key(api_key):
            await websocket.send_json({"type": "error", "text": "Invalid API key"})
            await websocket.close()
            return

        goal = payload.get("goal", payload.get("message", ""))
        if not goal:
            await websocket.send_json({"type": "error", "text": "Missing goal"})
            return

        async for event in stream_agent_thoughts(
            goal,
            provider=payload.get("llm_provider"),
            model=payload.get("llm_model"),
        ):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "text": str(e)})


# --- Chat ---


@app.post("/api/v1/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest, _key: dict = Depends(require_api_key)):
    command = parse_user_command(body.message, body.llm_provider, body.llm_model)
    scrape_result: Optional[ScrapeResponse] = None
    universal_result: Optional[dict[str, Any]] = None
    agent_result: Optional[dict[str, Any]] = None
    extra = None

    if body.execute_scrape and command.intent.value == "agent_research":
        agent_result = await run_agent(body.message, body.llm_provider, body.llm_model)
        extra = agent_result.get("synthesis", "")[:500]
    elif body.execute_scrape and command.urls:
        try:
            if command.scrape_mode in ("universal",) or command.intent.value == "universal_scrape":
                universal_result = universal_scrape(command.urls[0])
                extra = f"Scraper.io OK — {len(universal_result.get('items', []))} items"
            else:
                scrape_result = scrape_url(ScrapeRequest(url=command.urls[0], extract=command.extract))
                extra = f"Quick scrape OK — status {scrape_result.status_code}"
        except Exception as e:
            extra = f"Scrape failed: {e}"

    reply = build_chat_reply(command, extra)
    if body.json_only:
        return JSONResponse(content={
            "command": command.model_dump(),
            "scrape_result": scrape_result.model_dump() if scrape_result else None,
            "universal_result": universal_result,
            "agent_result": agent_result,
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
